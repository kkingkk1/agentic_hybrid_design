"""只读访问 P1 算法与案例条目，不执行条目代码。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Any


DEFAULT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "vault"
    / "Knowledge"
    / "P1-只读知识库校准"
)
ID_PATTERN = re.compile(r"(?:ALG|CASE)-[0-9]{3}\Z")
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
CASE_HASH_PATTERN = re.compile(r"SHA-256\s*为\s*`([0-9a-fA-F]{64})`")


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
    """提供完整候选目录和按 ID 加载，不负责选择、冻结或预算计量。"""

    def __init__(self, root: str | Path = DEFAULT_ROOT):
        self.root = Path(root)

    def _index(self) -> dict[str, Path]:
        index: dict[str, Path] = {}
        for folder, prefix in (("算法条目", "ALG-"), ("组合案例", "CASE-")):
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
        return index

    def _record(self, entry_id: str, directory: Path) -> tuple[dict[str, Any], bytes]:
        path = _inside(directory / f"{entry_id}.json", directory)
        raw = _read_bytes(path)
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
            _strings(record.get("function"), f"{entry_id}.function")
            _string(record.get("summary"), f"{entry_id}.summary")
        else:
            if set(record) != {"case_id", "category", "description", "code"}:
                raise LibraryError(f"{entry_id} 必须包含案例规定的四个字段")
            _string(record.get("category"), f"{entry_id}.category")
            _strings(record.get("code"), f"{entry_id}.code")
        return record, raw

    def catalog(self) -> dict[str, list[dict[str, Any]]]:
        """返回全部算法摘要及案例描述；此阶段不校验代码文件。"""
        result: dict[str, list[dict[str, Any]]] = {"algorithms": [], "cases": []}
        for entry_id, directory in self._index().items():
            record, _ = self._record(entry_id, directory)
            if entry_id.startswith("ALG-"):
                result["algorithms"].append({key: record[key] for key in (
                    "algorithm_id", "category", "function", "summary"
                )})
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
        index = self._index()
        missing = [entry_id for entry_id in ids if entry_id not in index]
        if missing:
            raise LibraryError(f"找不到条目: {', '.join(missing)}")

        loaded = []
        for entry_id in ids:
            directory = index[entry_id]
            record, raw = self._record(entry_id, directory)
            source_path = _inside(directory / f"{entry_id}.md", directory)
            source_raw = _read_bytes(source_path)
            source_text = _decode(source_raw, source_path)
            record["description"] = "".join(record["description"])

            if entry_id.startswith("ALG-"):
                self._load_algorithm_code(entry_id, directory, record)
            else:
                hashes = CASE_HASH_PATTERN.findall(source_text)
                if len(hashes) != 1:
                    raise LibraryError(f"{entry_id} 来源记录必须包含唯一的 JSON SHA-256")
                if hashlib.sha256(raw).hexdigest() != hashes[0].lower():
                    raise LibraryError(f"{entry_id} JSON SHA-256 与来源记录不一致")
                record["code"] = "\n".join(record["code"])

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

    @staticmethod
    def _load_algorithm_code(entry_id: str, directory: Path, record: dict[str, Any]) -> None:
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
            raw = _read_bytes(path)
            actual = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
            if actual != expected.lower():
                raise LibraryError(f"{entry_id} 代码 SHA-256 不一致: {item['path']}")
            item["content"] = _decode(raw, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读查看 P1 知识库候选和完整条目")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="知识库根目录")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="列出全部算法摘要与案例描述")
    load_parser = commands.add_parser("load", help="加载选定 ID 的正文、代码和来源")
    load_parser.add_argument("ids", nargs="+", help="一个或多个条目 ID")
    args = parser.parse_args(argv)
    try:
        reader = LibraryReader(args.root)
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
