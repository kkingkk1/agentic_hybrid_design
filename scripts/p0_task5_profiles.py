"""准备任务5的15个独立身份；执行前须获该清单的环境变更授权。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
from unittest.mock import patch
import uuid

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
    from . import p0_restricted_probe as restricted
    from . import p0_sandbox_runtime as runtime
    from . import p0_slot_setup as setup
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job
    import p0_restricted_probe as restricted
    import p0_sandbox_runtime as runtime
    import p0_slot_setup as setup


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "outputs" / "p0_task5_slots_plan_20261106_01.json"
NAMES = tuple(f"P0Task3Probe_20261106_{i:02d}" for i in range(1, 16))


def build_plan() -> dict:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA。")
    source = runtime._source_root()
    manifest, digest = setup._manifest()
    if os.path.normcase(os.path.normpath(str(source))) != os.path.normcase(os.path.normpath(manifest["source"])):
        raise ValueError("运行时来源与清单不一致。")
    targets = []
    for name in NAMES:
        package = Path(local) / "Packages" / name.lower()
        folder = package / "AC"
        targets.append({"name": name, "package_dir": str(package), "profile_dir": str(folder),
                        "runtime_dir": str(folder / identity.RUNTIME_DIR),
                        "profile_record": str(ROOT / "outputs" / f"p0_task3_appcontainer_task5_20261106_{name[-2:]}.jsonl")})
    sources = [Path(__file__), Path(setup.__file__), Path(restricted.__file__), Path(identity.__file__),
               Path(job.__file__), Path(runtime.__file__)]
    return {"purpose": "为P0任务5的15次独立冻结重跑准备身份；准备阶段只运行无害探针。",
            "host": socket.gethostname(), "source": str(source), "source_manifest": str(runtime.MANIFEST),
            "source_manifest_sha256": digest, "profile_count": len(targets),
            "program_sources_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
            "runtime_files_per_profile": manifest["file_count"], "runtime_bytes_per_profile": manifest["bytes_per_identity"],
            "total_runtime_files": len(targets) * manifest["file_count"],
            "total_runtime_bytes": len(targets) * manifest["bytes_per_identity"], "targets": targets,
            "effect": "为当前用户新建15个AppContainer配置与各自目录，复制已有CPython标准库；不联网、不提权、不改已有ACL。",
            "retention": "配置、运行时及探针记录保留；清理须另列精确目标并取得确认。"}


def execute(plan: dict, save) -> dict:
    with patch.object(setup, "PLAN", PLAN), patch.object(setup, "build_plan", side_effect=build_plan):
        return setup.execute(plan, save)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true")
    options = parser.parse_args()
    if options.plan:
        plan = build_plan()
        with PLAN.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"plan": str(PLAN), "profiles": plan["profile_count"],
                          "files": plan["total_runtime_files"], "bytes": plan["total_runtime_bytes"]}))
        return 0
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    record = ROOT / "outputs" / f"p0_task5_slots_execution_{uuid.uuid4().hex}.jsonl"
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
