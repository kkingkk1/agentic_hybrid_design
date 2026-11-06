"""准备 P0 的16个新测试身份；执行前须取得对应环境变更授权。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import threading
import uuid

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
    from . import p0_sandbox_runtime as runtime
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job
    import p0_sandbox_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "outputs" / "p0_task3_slots_plan_20261105_04.json"
NAMES = tuple(f"P0Task3Probe_20261105_{index:02d}" for index in range(3, 19))


def _manifest() -> tuple[dict, str]:
    raw = runtime.MANIFEST.read_bytes()
    manifest = json.loads(raw)
    if (manifest.get("python_version") != "3.13.12"
            or manifest.get("file_count") != len(manifest.get("files", []))
            or manifest.get("bytes_per_identity") != sum(item["bytes"] for item in manifest["files"])):
        raise ValueError("运行时来源清单不完整。")
    paths = set()
    for item in manifest["files"]:
        runtime._relative_path(item["path"])
        normalized = item["path"].casefold()
        if (normalized in paths or type(item["bytes"]) is not int or item["bytes"] < 0
                or not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in item["sha256"])):
            raise ValueError("运行时来源清单含重复或无效条目。")
        paths.add(normalized)
    return manifest, hashlib.sha256(raw).hexdigest()


def build_plan() -> dict:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA。")
    source = runtime._source_root()
    manifest, digest = _manifest()
    if os.path.normcase(os.path.normpath(str(source))) != os.path.normcase(os.path.normpath(manifest["source"])):
        raise ValueError("运行时来源与清单不一致。")
    targets = []
    for name in NAMES:
        package = Path(local) / "Packages" / name.lower()
        folder = package / "AC"
        targets.append({"name": name, "package_dir": str(package), "profile_dir": str(folder),
                        "runtime_dir": str(folder / identity.RUNTIME_DIR),
                        "profile_record": str(ROOT / "outputs" / f"p0_task3_appcontainer_profile_20261105_{name[-2:]}.jsonl")})
    programs = [Path(__file__), ROOT / "scripts" / "p0_slot_verify.py",
                ROOT / "scripts" / "p0_restricted_probe.py", Path(identity.__file__),
                Path(job.__file__), Path(runtime.__file__)]
    return {"purpose": "准备P0任务3的16个新测试身份，不运行候选。",
            "host": socket.gethostname(), "source": str(source), "source_manifest": str(runtime.MANIFEST),
            "source_manifest_sha256": digest, "profile_count": len(targets),
            "program_sources_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in programs},
            "runtime_files_per_profile": manifest["file_count"], "runtime_bytes_per_profile": manifest["bytes_per_identity"],
            "total_runtime_files": len(targets) * manifest["file_count"],
            "total_runtime_bytes": len(targets) * manifest["bytes_per_identity"],
            "targets": targets,
            "effect": "为当前用户新建指定AppContainer配置及默认目录；复制既有Python标准库，不安装依赖或修改已有ACL。",
            "retention": "身份和运行时保留；清理须另列精确目标并取得确认。"}


def _preflight(plan: dict) -> tuple[dict, Path]:
    if plan != build_plan():
        raise ValueError("准备清单或来源已改变，停止执行。")
    manifest, _ = _manifest()
    if runtime.build_manifest() != manifest:
        raise ValueError("当前解释器与已审查清单不一致。")
    source = runtime._source_root()
    packages = Path(os.environ["LOCALAPPDATA"]) / "Packages"
    runtime._safe_stat(packages)
    if shutil.disk_usage(packages).free < plan["total_runtime_bytes"]:
        raise OSError("磁盘可用空间不足。")
    plan_digest = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    for target in plan["targets"]:
        package, record = Path(target["package_dir"]), Path(target["profile_record"])
        if package.exists() != record.exists():
            raise FileExistsError(f"身份目录和记录不匹配，停止：{target['name']}")
        if record.exists():
            _check_plan_provenance(record, plan_digest)
            profile = identity._recorded_profile(record.name)
            if (profile["profile_name"] != target["name"] or
                    os.path.normcase(os.path.normpath(profile["profile_folder"])) !=
                    os.path.normcase(os.path.normpath(target["profile_dir"]))):
                raise ValueError(f"既有记录与目标不一致：{target['name']}")
    return manifest, source


def _check_plan_provenance(record: Path, expected_digest: str) -> None:
    raw = record.read_bytes()
    if len(raw) > 65536:
        raise ValueError("身份来源记录过大。")
    try:
        first = json.loads(raw.splitlines()[0])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("身份来源记录不完整。") from exc
    if (not isinstance(first, dict) or first.get("event") != "source"
            or first.get("plan_sha256") != expected_digest):
        raise ValueError("已有身份不属于本准备清单，不复用。")


def _create_profile(target: dict, plan_digest: str) -> dict:
    record = Path(target["profile_record"])
    if record.exists():
        _check_plan_provenance(record, plan_digest)
        return identity._recorded_profile(record.name)
    with record.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        save({"event": "source", "sha256": hashlib.sha256(Path(identity.__file__).read_bytes()).hexdigest(),
              "plan_sha256": plan_digest})
        try:
            result = identity.run_probe(profile_name=target["name"], sink=save)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    if result.get("passed") is not True:
        raise OSError(f"身份创建或无害自检失败：{target['name']}")
    return identity._recorded_profile(record.name)


def _copy_runtime(profile: dict, target: dict, source: Path, manifest: dict, stop: threading.Event) -> dict:
    folder = Path(profile["profile_folder"])
    if os.path.normcase(os.path.normpath(folder)) != os.path.normcase(os.path.normpath(target["profile_dir"])):
        raise ValueError("新身份目录与准备清单不一致。")
    for path in (folder.parent.parent, folder.parent, folder):
        runtime._safe_stat(path)
    destination = Path(target["runtime_dir"])
    destination.mkdir(exist_ok=True)
    runtime._safe_stat(destination)
    copied = reused = 0
    for item in manifest["files"]:
        if stop.is_set():
            raise OSError("其他作业失败，停止复制并保留现有文件。")
        relative = runtime._relative_path(item["path"])
        src, dst = source / relative, destination / relative
        parent = destination
        for part in relative.parts[:-1]:
            parent = parent / part
            parent.mkdir(exist_ok=True)
            runtime._safe_stat(parent)
        runtime._safe_stat(src)
        if dst.exists():
            runtime._safe_stat(dst)
            if dst.stat().st_size != item["bytes"] or runtime._sha256(dst) != item["sha256"]:
                raise OSError(f"已有文件与来源不一致，不覆盖：{dst}")
            reused += 1
            continue
        digest = hashlib.sha256()
        with src.open("rb") as input_stream, dst.open("xb") as output_stream:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                digest.update(chunk)
                output_stream.write(chunk)
        if digest.hexdigest() != item["sha256"] or dst.stat().st_size != item["bytes"]:
            raise OSError(f"复制结果与来源不一致：{dst}")
        copied += 1
    verified = runtime._verify_copied(destination, manifest)
    return {"name": target["name"], "runtime_dir": str(destination), "copied": copied, "reused": reused,
            "verified": verified}


def execute(plan: dict, sink) -> dict:
    manifest, source = _preflight(plan)
    plan_digest = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    stop = threading.Event()
    lock = threading.Lock()

    def worker(target):
        try:
            resources = job._resource_gate()
            if stop.is_set():
                raise OSError("其他作业失败，未开始身份创建。")
            profile = _create_profile(target, plan_digest)
            copied = _copy_runtime(profile, target, source, manifest, stop)
            outcome = {"passed": True, "resources": resources, **copied}
        except Exception as exc:
            stop.set()
            outcome = {"passed": False, "name": target["name"], "error": f"{type(exc).__name__}: {exc}"}
        with lock:
            sink({"event": "profile", "result": outcome})
        return outcome

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(plan["targets"])) as pool:
        results = list(pool.map(worker, plan["targets"]))
    return {"passed": all(result["passed"] for result in results), "profiles": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="P0测试身份准备；--execute 须先取得用户授权。")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="只生成准备清单，不创建身份或复制文件")
    mode.add_argument("--execute", action="store_true", help="执行已审查的准备清单")
    options = parser.parse_args()
    if options.plan:
        plan = build_plan()
        with PLAN.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"plan": str(PLAN), "profile_count": plan["profile_count"],
                          "total_runtime_files": plan["total_runtime_files"],
                          "total_runtime_bytes": plan["total_runtime_bytes"]}, ensure_ascii=True))
        return 0
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    record = ROOT / "outputs" / f"p0_task3_slots_execution_{uuid.uuid4().hex}.jsonl"
    with record.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        save({"event": "plan", "path": str(PLAN), "sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest()})
        try:
            result = execute(plan, save)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps({"passed": result["passed"], "record": str(record)}, ensure_ascii=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
