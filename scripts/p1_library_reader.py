"""只读访问 P1 算法与案例条目，不执行条目代码。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = PROJECT_ROOT / "library"
DRAFT_ROOT = LIBRARY_ROOT / "working" / "calibration"
FROZEN_DIR = LIBRARY_ROOT / "manifests" / "calibration-20261114-03-en"
DEFAULT_ROOT = LIBRARY_ROOT / "versions" / "calibration-20261114-03-en"
DEFAULT_MANIFEST = FROZEN_DIR / (
    "manifest-6e20a83e63570d7f9ae40ddfece9cc86c63e73b5db8078b7a987a562d00f2d26.json"
)
ID_PATTERN = re.compile(r"(?:ALG|CASE)-[0-9]{3}\Z")
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
CASE_HASH_PATTERN = re.compile(r"SHA-256\s*(?:为|is)\s*`([0-9a-fA-F]{64})`")
MANIFEST_NAME_PATTERN = re.compile(r"manifest-([0-9a-f]{64})\.json\Z")


class LibraryError(Exception):
    """条目缺失、格式不符或版本核对失败。"""


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise LibraryError(f"无法读取 {path}: {exc}") from exc


def _decode(raw: bytes, path: Path) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LibraryError(f"文件不是有效的 UTF-8: {path}") from exc


def _inside(path: Path, directory: Path) -> Path:
    """解析符号链接后确认文件仍处于预期目录。"""
    try:
        resolved = path.resolve(strict=True)
        parent = directory.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LibraryError(f"无法定位 {path}: {exc}") from exc
    if not resolved.is_relative_to(parent):
        raise LibraryError(f"路径超出条目目录: {path}")
    return resolved


def _code_path(directory: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise LibraryError(f"代码路径无效: {value!r}")
    windows = PureWindowsPath(value)
    parts = re.split(r"[/\\]", value)
    if windows.drive or windows.root or any(part in ("", ".", "..") for part in parts):
        raise LibraryError(f"代码路径必须位于条目目录内: {value!r}")
    return _inside(directory.joinpath(*parts), directory)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LibraryError(f"{label} 必须是非空字符串")
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(x, str) for x in value):
        raise LibraryError(f"{label} 必须是非空字符串数组")
    return value


class LibraryReader:
    """按冻结清单读取候选及条目；不负责选择、创建快照或预算计量。"""

    def __init__(self, root: str | Path = DEFAULT_ROOT, *,
                 manifest: str | Path | None = DEFAULT_MANIFEST):
        self.root = Path(root)
        self.manifest = Path(manifest) if manifest is not None else None

    def _manifest(self) -> dict[str, Any] | None:
        if self.manifest is None:
            return None
        match = MANIFEST_NAME_PATTERN.fullmatch(self.manifest.name)
        if match is None:
            raise LibraryError("冻结清单文件名必须包含其 SHA-256")
        raw = _read_bytes(self.manifest)
        if hashlib.sha256(raw).hexdigest() != match.group(1):
            raise LibraryError("冻结清单 SHA-256 与文件名不一致")
        try:
            manifest = json.loads(_decode(raw, self.manifest))
        except json.JSONDecodeError as exc:
            raise LibraryError(f"冻结清单 JSON 无效: {self.manifest}: {exc}") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != "p1-library-freeze-v1":
            raise LibraryError("冻结清单格式无效")
        entries = manifest.get("entries")
        files = manifest.get("files")
        if (not isinstance(entries, list) or not entries
                or any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in entries)
                or len(entries) != len(set(entries)) or not isinstance(files, dict)):
            raise LibraryError("冻结清单的条目或文件列表无效")
        for path, info in files.items():
            if (not isinstance(path, str) or not path or not isinstance(info, dict)
                    or not isinstance(info.get("sha256"), str)
                    or not HASH_PATTERN.fullmatch(info["sha256"])
                    or type(info.get("size")) is not int or info["size"] < 0):
                raise LibraryError(f"冻结文件记录无效: {path!r}")
        return manifest

    def _read_material(self, path: Path, manifest: dict[str, Any] | None) -> bytes:
        raw = _read_bytes(path)
        if manifest is None:
            return raw
        try:
            relative = path.relative_to(self.root.resolve(strict=True)).as_posix()
        except (ValueError, OSError, RuntimeError) as exc:
            raise LibraryError(f"冻结文件路径不在知识库内: {path}") from exc
        expected = manifest["files"].get(relative)
        if expected is None:
            raise LibraryError(f"文件未登记在冻结清单中: {relative}")
        if (len(raw) != expected["size"]
                or hashlib.sha256(raw).hexdigest() != expected["sha256"].lower()):
            raise LibraryError(f"冻结文件 SHA-256 不一致: {relative}")
        return raw

    def _index(self, manifest: dict[str, Any] | None = None) -> dict[str, Path]:
        index: dict[str, Path] = {}
        current = (("algorithms", "ALG-"), ("cases", "CASE-"))
        legacy = (("算法条目", "ALG-"), ("组合案例", "CASE-"))
        has_current = any((self.root / folder).exists() for folder, _ in current)
        has_legacy = any((self.root / folder).exists() for folder, _ in legacy)
        if has_current and has_legacy:
            raise LibraryError("知识库不能混用新旧条目目录")
        for folder, prefix in current if has_current else legacy:
            base = self.root / folder
            _inside(base, self.root)
            try:
                children = sorted(base.iterdir(), key=lambda item: item.name)
            except OSError as exc:
                raise LibraryError(f"无法读取条目目录 {base}: {exc}") from exc
            for child in children:
                if not child.name.startswith(("ALG-", "CASE-")):
                    continue
                if (not child.name.startswith(prefix) or not child.is_dir()
                        or not ID_PATTERN.fullmatch(child.name)):
                    raise LibraryError(f"条目目录名称或类型无效: {child}")
                _inside(child, base)
                if child.name in index:
                    raise LibraryError(f"重复条目 ID: {child.name}")
                index[child.name] = child
        if manifest is not None and set(index) != set(manifest["entries"]):
            missing = sorted(set(manifest["entries"]) - set(index))
            extra = sorted(set(index) - set(manifest["entries"]))
            raise LibraryError(f"条目集合与冻结清单不一致: 缺失={missing}, 新增={extra}")
        return index

    def _record(self, entry_id: str, directory: Path,
                manifest: dict[str, Any] | None) -> tuple[dict[str, Any], bytes]:
        path = _inside(directory / f"{entry_id}.json", directory)
        raw = self._read_material(path, manifest)
        try:
            record = json.loads(_decode(raw, path))
        except json.JSONDecodeError as exc:
            raise LibraryError(f"JSON 无效: {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise LibraryError(f"条目必须是 JSON 对象: {path}")
        key = "algorithm_id" if entry_id.startswith("ALG-") else "case_id"
        if record.get(key) != entry_id:
            raise LibraryError(f"条目 ID 与目录不一致: {path}")
        _strings(record.get("description"), f"{entry_id}.description")
        if key == "algorithm_id":
            _strings(record.get("category"), f"{entry_id}.category")
            # 旧快照保留原字段，新条目无需功能标签。
            if "function" in record:
                _strings(record["function"], f"{entry_id}.function")
            _string(record.get("summary"), f"{entry_id}.summary")
        else:
            if set(record) != {"case_id", "category", "description", "code"}:
                raise LibraryError(f"{entry_id} 必须包含案例规定的四个字段")
            _string(record.get("category"), f"{entry_id}.category")
            code = record.get("code")
            if not isinstance(code, list) or not code or not (
                all(isinstance(item, str) for item in code)
                or all(isinstance(item, dict) for item in code)
            ):
                raise LibraryError(f"{entry_id}.code 必须是代码行数组或文件清单")
        return record, raw

    def catalog(self) -> dict[str, list[dict[str, Any]]]:
        """返回全部候选；冻结模式校验条目集合和候选 JSON。"""
        result: dict[str, list[dict[str, Any]]] = {"algorithms": [], "cases": []}
        manifest = self._manifest()
        for entry_id, directory in self._index(manifest).items():
            record, _ = self._record(entry_id, directory, manifest)
            if entry_id.startswith("ALG-"):
                keys = ("algorithm_id", "category", "function", "summary") if "function" in record else (
                    "algorithm_id", "category", "summary"
                )
                result["algorithms"].append({key: record[key] for key in keys})
            else:
                result["cases"].append({
                    "case_id": entry_id,
                    "category": record["category"],
                    "description": "".join(record["description"]),
                })
        return result

    def load(self, ids: list[str]) -> list[dict[str, Any]]:
        """按请求顺序加载完整描述、代码及来源，任何一条失败即报错。"""
        if not isinstance(ids, list) or any(
            not isinstance(value, str) or not ID_PATTERN.fullmatch(value) for value in ids
        ):
            raise LibraryError("ID 必须是 ALG- 或 CASE- 加三位数字")
        if len(ids) != len(set(ids)):
            raise LibraryError("所选 ID 存在重复")
        manifest = self._manifest()
        index = self._index(manifest)
        missing = [entry_id for entry_id in ids if entry_id not in index]
        if missing:
            raise LibraryError(f"找不到条目: {', '.join(missing)}")

        loaded = []
        for entry_id in ids:
            directory = index[entry_id]
            record, raw = self._record(entry_id, directory, manifest)
            source_path = _inside(directory / f"{entry_id}.md", directory)
            source_raw = self._read_material(source_path, manifest)
            source_text = _decode(source_raw, source_path)
            record["description"] = "".join(record["description"])

            if entry_id.startswith("ALG-"):
                self._load_algorithm_code(entry_id, directory, record, manifest)
            else:
                hashes = CASE_HASH_PATTERN.findall(source_text)
                if len(hashes) != 1:
                    raise LibraryError(f"{entry_id} 来源记录必须包含唯一的 JSON SHA-256")
                if hashlib.sha256(raw).hexdigest() != hashes[0].lower():
                    raise LibraryError(f"{entry_id} JSON SHA-256 与来源记录不一致")
                if isinstance(record["code"][0], str):
                    record["code"] = "\n".join(record["code"])
                else:
                    record["code"] = self._load_case_code(entry_id, directory, record["code"], index, manifest)

            loaded.append({
                "entry": record,
                "json_file": {
                    "path": (directory / f"{entry_id}.json").relative_to(self.root).as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
                "source": {
                    "path": (directory / f"{entry_id}.md").relative_to(self.root).as_posix(),
                    "sha256": hashlib.sha256(source_raw).hexdigest(),
                    "content": source_text,
                },
            })
        return loaded

    def _load_case_code(
        self, entry_id: str, directory: Path, files: list[dict[str, Any]], index: dict[str, Path],
        manifest: dict[str, Any] | None,
    ) -> str:
        """按清单组装案例；跨条目引用只能指向已登记的算法文件。"""
        result: list[str] = []
        names: set[str] = set()
        algorithms: dict[str, dict[str, Any]] = {}
        for item in files:
            keys = {"name", "path", "sha256_lf"}
            if "algorithm_id" in item:
                keys.add("algorithm_id")
            if "marker" in item:
                keys.add("marker")
            if set(item) != keys:
                raise LibraryError(f"{entry_id} 案例代码文件字段无效")
            marker = item.get("marker", "//")
            if marker not in ("//", "#"):
                raise LibraryError(f"{entry_id} 案例文件标记无效: {marker!r}")
            name = _string(item.get("name"), f"{entry_id}.code.name")
            windows = PureWindowsPath(name)
            if (windows.drive or windows.root or "\\" in name
                    or any(part in ("", ".", "..") for part in name.split("/"))
                    or any(ord(ch) < 32 or ch in '<>:"|?*' for ch in name)):
                raise LibraryError(f"{entry_id} 案例文件名无效: {name!r}")
            if name.casefold() in names:
                raise LibraryError(f"{entry_id} 案例文件名重复: {name}")
            names.add(name.casefold())
            expected = item.get("sha256_lf")
            if not isinstance(expected, str) or not HASH_PATTERN.fullmatch(expected):
                raise LibraryError(f"{entry_id} 案例文件的 sha256_lf 无效: {name}")

            if "algorithm_id" in item:
                algorithm_id = item["algorithm_id"]
                if (not isinstance(algorithm_id, str)
                        or not re.fullmatch(r"ALG-[0-9]{3}", algorithm_id)
                        or algorithm_id not in index):
                    raise LibraryError(f"{entry_id} 引用的算法 ID 无效: {algorithm_id!r}")
                if algorithm_id not in algorithms:
                    algorithm, _ = self._record(algorithm_id, index[algorithm_id], manifest)
                    self._load_algorithm_code(algorithm_id, index[algorithm_id], algorithm, manifest)
                    algorithms[algorithm_id] = algorithm
                candidates = [f for f in algorithms[algorithm_id]["code"]["files"]
                              if f["path"] == item["path"]]
                if len(candidates) != 1:
                    raise LibraryError(f"{entry_id} 引用的算法文件未登记: {item['path']!r}")
                source = candidates[0]
                if source["sha256_lf"].lower() != expected.lower():
                    raise LibraryError(f"{entry_id} 引用的算法文件 SHA-256 与锁定版本不一致: {name}")
                content = source["content"]
            else:
                path = _code_path(directory, item.get("path"))
                raw = self._read_material(path, manifest)
                if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != expected.lower():
                    raise LibraryError(f"{entry_id} 案例文件 SHA-256 不一致: {name}")
                content = _decode(raw, path)
            result.extend((f"{marker} --- FILE: {name} ---", content.replace("\r\n", "\n")))
        return "\n".join(result)

    def _load_algorithm_code(self, entry_id: str, directory: Path, record: dict[str, Any],
                             manifest: dict[str, Any] | None) -> None:
        code = record.get("code")
        if not isinstance(code, dict):
            raise LibraryError(f"{entry_id}.code 必须是对象")
        for key in ("entry", "language", "origin"):
            _string(code.get(key), f"{entry_id}.code.{key}")
        files = code.get("files")
        if not isinstance(files, list) or not files:
            raise LibraryError(f"{entry_id}.code.files 必须包含代码文件")
        paths: set[Path] = set()
        for item in files:
            if not isinstance(item, dict):
                raise LibraryError(f"{entry_id} 代码文件记录必须是对象")
            path = _code_path(directory, item.get("path"))
            if path in paths:
                raise LibraryError(f"{entry_id} 代码文件重复: {item['path']}")
            paths.add(path)
            expected = item.get("sha256_lf")
            if not isinstance(expected, str) or not HASH_PATTERN.fullmatch(expected):
                raise LibraryError(f"{entry_id} 的 sha256_lf 无效: {item['path']}")
            raw = self._read_material(path, manifest)
            actual = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
            if actual != expected.lower():
                raise LibraryError(f"{entry_id} 代码 SHA-256 不一致: {item['path']}")
            item["content"] = _decode(raw, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读查看 P1 知识库候选和完整条目")
    parser.add_argument("--root", type=Path, help="知识库根目录；未指定时按读取模式选择")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="指定冻结版本清单")
    mode.add_argument("--draft", action="store_true", help="读取未冻结的本地草稿，不用于冻结批次")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="列出全部算法摘要与案例描述")
    load_parser = commands.add_parser("load", help="加载选定 ID 的正文、代码和来源")
    load_parser.add_argument("ids", nargs="+", help="一个或多个条目 ID")
    args = parser.parse_args(argv)
    try:
        root = args.root if args.root is not None else (DRAFT_ROOT if args.draft else DEFAULT_ROOT)
        reader = LibraryReader(root, manifest=None if args.draft else args.manifest)
        result = reader.catalog() if args.command == "catalog" else reader.load(args.ids)
    except LibraryError as exc:
        print(f"读取失败: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    # Windows 重定向输出时也使用 UTF-8，避免 JSON 随系统代码页变化。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
