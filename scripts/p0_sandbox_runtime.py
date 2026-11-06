"""清点并按显式授权复制现有 CPython 标准库到两个测试身份的专用目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "outputs" / "p0_task3_runtime_manifest_20261105_01.json"
COPY_RECORD = ROOT / "outputs" / "p0_task3_runtime_copy_20261105_01.jsonl"
RESUME_RECORD = ROOT / "outputs" / "p0_task3_runtime_copy_20261105_02.jsonl"
DIRECT_RECORD = ROOT / "outputs" / "p0_task3_runtime_copy_20261105_03.jsonl"
DIRECT_SMOKE_RECORD = ROOT / "outputs" / "p0_task3_appcontainer_boundary_runtime_direct_20261105_03.jsonl"
RUNTIME_DIR = identity.RUNTIME_DIR
ROOT_FILES = ("python.exe", "python3.dll", "python313.dll", "vcruntime140.dll", "vcruntime140_1.dll")
SUBTREES = ("Lib", "DLLs")
SKIP_DIRS = {"site-packages", "__pycache__"}


def _safe_stat(path: Path):
    info = path.lstat()
    if info.st_file_attributes & 0x400:
        raise OSError(f"不复制重解析点：{path}")
    return info


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_root() -> Path:
    if sys.version_info[:3] != (3, 13, 12):
        raise OSError("当前解释器版本不符合 P0 合同。")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA，不能定位现有解释器。")
    expected = Path(local) / "Programs" / "Python" / "Python313" / "python.exe"
    if os.path.normcase(os.path.normpath(sys.executable)) != os.path.normcase(os.path.normpath(expected)):
        raise OSError("当前解释器路径与已选的 CPython 不一致。")
    _safe_stat(expected.parent)
    _safe_stat(expected)
    return expected.parent


def _relative_path(name: str) -> Path:
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("运行时清单路径无效。")
    path = PurePosixPath(name)
    if (path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts)
            or path.parts[0] not in (*ROOT_FILES, *SUBTREES)
            or any(part in SKIP_DIRS for part in path.parts)
            or name.endswith((".pyc", ".pyo"))):
        raise ValueError("运行时清单包含不允许的路径。")
    if path.parts[0] in ROOT_FILES and len(path.parts) != 1:
        raise ValueError("运行时根文件路径无效。")
    return Path(*path.parts)


def build_manifest() -> dict:
    source = _source_root()
    paths = []
    for name in ROOT_FILES:
        file = source / name
        if not file.is_file():
            raise OSError(f"缺少现有运行时文件：{file}")
        _safe_stat(file)
        paths.append(file)
    for name in SUBTREES:
        tree = source / name
        _safe_stat(tree)
        if not tree.is_dir():
            raise OSError(f"缺少现有标准库目录：{tree}")
        for current, dirs, files in os.walk(tree, followlinks=False):
            current_path = Path(current)
            _safe_stat(current_path)
            dirs[:] = sorted(item for item in dirs if item not in SKIP_DIRS)
            for dirname in dirs:
                _safe_stat(current_path / dirname)
            for filename in sorted(files):
                if filename.endswith((".pyc", ".pyo")):
                    continue
                path = current_path / filename
                _safe_stat(path)
                if not path.is_file():
                    raise OSError(f"运行时来源不是普通文件：{path}")
                paths.append(path)
    files = []
    for path in sorted(paths, key=lambda item: item.relative_to(source).as_posix()):
        relative = path.relative_to(source).as_posix()
        _relative_path(relative)
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return {"source": str(source), "python_version": "3.13.12", "excluded": sorted(SKIP_DIRS) + ["*.pyc", "*.pyo"],
            "files": files, "file_count": len(files), "bytes_per_identity": sum(item["bytes"] for item in files)}


def _destinations(resume_first: bool = False, direct: bool = False) -> list[tuple[dict, Path]]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA。")
    destinations = []
    sids = set()
    for index, (name, record) in enumerate(identity.PROFILE_RECORDS.items()):
        profile = identity._recorded_profile(record)
        expected = Path(local) / "Packages" / name.lower() / "AC"
        actual = Path(profile["profile_folder"])
        if (profile["profile_name"] != name or os.path.normcase(os.path.normpath(actual))
                != os.path.normcase(os.path.normpath(expected))):
            raise ValueError("测试身份目录与创建记录不一致。")
        for path in (actual.parent.parent, actual.parent, actual):
            _safe_stat(path)
        if profile["profile_sid"] in sids:
            raise ValueError("测试身份的SID不互异。")
        sids.add(profile["profile_sid"])
        target = actual / RUNTIME_DIR
        if target.exists() and not (resume_first and index == 0):
            raise FileExistsError(f"目标已存在，不覆盖：{target}")
        if resume_first and index == 0 and not target.is_dir():
            raise OSError("第一个运行时目录不存在，不能从记录恢复。")
        if not (direct and index == 0):
            if direct:
                diagnostic = ROOT / "outputs" / f"p0_task3_runtime_direct_{name[-2:]}_20261105_01.txt"
            else:
                version = "02" if resume_first and index == 0 else "01"
                diagnostic = ROOT / "outputs" / f"p0_task3_runtime_smoke_{name[-2:]}_20261105_{version}.txt"
            if diagnostic.exists():
                raise FileExistsError(f"诊断记录已存在，不覆盖：{diagnostic}")
        destinations.append((profile, target))
    return destinations


def _verify_copied(destination: Path, manifest: dict) -> int:
    expected = {item["path"]: item for item in manifest["files"]}
    seen = set()
    _safe_stat(destination)
    for current, dirs, files in os.walk(destination, followlinks=False):
        directory = Path(current)
        _safe_stat(directory)
        for dirname in dirs:
            _safe_stat(directory / dirname)
        for filename in files:
            path = directory / filename
            _safe_stat(path)
            relative = path.relative_to(destination).as_posix()
            if relative not in expected or not path.is_file():
                raise OSError(f"已复制运行时中存在清单外文件：{path}")
            item = expected[relative]
            if path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
                raise OSError(f"已复制运行时的哈希或大小不一致：{path}")
            seen.add(relative)
    if seen != set(expected):
        raise OSError("已复制运行时的文件清单不完整。")
    return len(seen)


def _verify_resume_record(destination: Path, manifest: dict) -> str:
    raw = COPY_RECORD.read_bytes()
    if len(raw) > 65536:
        raise ValueError("首次复制记录过大。")
    events = [json.loads(line) for line in raw.splitlines()]
    if [event.get("event") for event in events] != ["sources", "destination_created", "destination_verified",
                                                      "runtime_smoke", "result"]:
        raise ValueError("首次复制记录不完整。")
    source, created, verified, smoke, result = events
    if (source.get("manifest_sha256") != hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
            or created.get("path") != str(destination) or verified.get("path") != str(destination)
            or verified.get("verified_files") != manifest["file_count"]
            or smoke.get("profile") != "P0Task3Probe_20261105_01"
            or smoke.get("result", {}).get("passed") is not False
            or result.get("result", {}).get("passed") is not False):
        raise ValueError("首次复制记录与待恢复的目录不一致。")
    return hashlib.sha256(raw).hexdigest()


def _verify_direct_smoke(profile: dict, manifest: dict) -> tuple[dict, str]:
    raw = DIRECT_SMOKE_RECORD.read_bytes()
    if len(raw) > 65536:
        raise ValueError("直接启动记录过大。")
    events = [json.loads(line) for line in raw.splitlines()]
    if [event.get("event") for event in events] != ["sources", "destination_reverified", "result"]:
        raise ValueError("直接启动记录不完整。")
    result = events[-1].get("result", {})
    probe = result.get("probe", {})
    diagnostic = ROOT / "outputs" / "p0_task3_runtime_direct_01_20261105_03.txt"
    if (result.get("passed") is not True or result.get("verified_files") != manifest["file_count"]
            or probe.get("profile_name") != profile["profile_name"]
            or probe.get("identity_verified") is not True or probe.get("exit_code") != 0
            or probe.get("runtime_evidence", {}).get("passed") is not True
            or probe.get("diagnostic_path") != str(diagnostic)):
        raise ValueError("直接启动记录未能证明指定身份及运行时通过自检。")
    with diagnostic.open("rb") as stream:
        actual = stream.read(4096).decode("mbcs", errors="replace")
    if not identity._runtime_evidence(actual, profile)["passed"]:
        raise ValueError("直接启动输出未能证明运行时版本和模块来源。")
    return probe, hashlib.sha256(raw).hexdigest()


def copy_runtime(manifest: dict, sink, resume_first: bool = False, direct: bool = False) -> dict:
    if direct and not resume_first:
        raise ValueError("直接启动恢复必须复核第一份运行时。")
    fresh = build_manifest()
    if fresh != manifest:
        raise ValueError("现有解释器文件与已审查清单不一致；停止复制。")
    resources = job._resource_gate()
    destinations = _destinations(resume_first, direct)
    source = _source_root()
    if shutil.disk_usage(destinations[0][1].parent).free < 2 * manifest["bytes_per_identity"]:
        raise OSError("本地空间不足以保存两份运行时。")
    result = {"passed": False, "file_count_per_identity": manifest["file_count"],
              "bytes_per_identity": manifest["bytes_per_identity"], "resource_precheck": resources,
              "destinations": []}
    for index, (profile, destination) in enumerate(destinations):
        if resume_first and index == 0:
            record_sha = _verify_resume_record(destination, manifest)
            copied = _verify_copied(destination, manifest)
            sink({"event": "destination_reverified", "path": str(destination), "verified_files": copied,
                  "previous_record_sha256": record_sha})
        else:
            destination.mkdir()  # 不覆盖已有目录；失败时保留已写入的文件。
            sink({"event": "destination_created", "path": str(destination)})
            copied = 0
            for item in manifest["files"]:
                relative = _relative_path(item["path"])
                src, dst = source / relative, destination / relative
                parent = destination
                for part in relative.parts[:-1]:
                    parent = parent / part
                    parent.mkdir(exist_ok=True)
                    _safe_stat(parent)
                _safe_stat(src)
                digest = hashlib.sha256()
                with src.open("rb") as input_stream, dst.open("xb") as output_stream:
                    for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        output_stream.write(chunk)
                if (digest.hexdigest() != item["sha256"] or dst.stat().st_size != item["bytes"]
                        or _sha256(dst) != item["sha256"]):
                    raise OSError(f"复制后哈希或大小不一致：{dst}")
                copied += 1
            sink({"event": "destination_verified", "path": str(destination), "verified_files": copied})
        if direct and index == 0:
            smoke, smoke_sha = _verify_direct_smoke(profile, manifest)
            sink({"event": "runtime_smoke_reused", "profile": profile["profile_name"],
                  "record_sha256": smoke_sha})
        else:
            action = ("owned_python_direct" if direct else
                      "owned_python_smoke_retry" if resume_first and index == 0 else "owned_python_smoke")
            smoke = identity.run_probe(reused_profile=profile, action=action)
            sink({"event": "runtime_smoke", "profile": profile["profile_name"], "result": smoke})
        if smoke.get("passed") is not True:
            raise OSError(f"隔离身份的运行时自检失败：{profile['profile_name']}")
        result["destinations"].append({"path": str(destination), "verified_files": copied, "smoke": smoke})
    result["passed"] = len(result["destinations"]) == 2
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="仅操作现有 CPython 和两个指定的任务3测试身份。")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="新建可审查的源码文件清单，不复制")
    mode.add_argument("--copy", action="store_true", help="经授权后按清单复制，不覆盖也不自动删除")
    mode.add_argument("--resume-first", action="store_true", help="复核首次失败记录和第一份文件后继续")
    mode.add_argument("--resume-direct", action="store_true", help="复核直接启动结果并继续第二份复制")
    options = parser.parse_args()
    if options.plan:
        manifest = build_manifest()
        with MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=True, sort_keys=True, indent=2)
        print(json.dumps({"manifest": str(MANIFEST), "files": manifest["file_count"],
                          "bytes_per_identity": manifest["bytes_per_identity"]}))
        return 0
    record = DIRECT_RECORD if options.resume_direct else RESUME_RECORD if options.resume_first else COPY_RECORD
    with record.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        try:
            raw = MANIFEST.read_bytes()
            manifest = json.loads(raw)
            save({"event": "sources", "script_sha256": _sha256(Path(__file__)),
                  "manifest_sha256": hashlib.sha256(raw).hexdigest()})
            result = copy_runtime(manifest, save, resume_first=options.resume_first or options.resume_direct,
                                  direct=options.resume_direct)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
