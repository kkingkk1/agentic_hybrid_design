"""以两个已授权测试身份验证真实 solver.py 文件入口；不运行模型候选。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from unittest.mock import patch

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_sandbox_exec as sandbox
    from . import p0_sandbox_runtime as runtime
    from . import p0_tsp_evaluator as evaluator
else:
    import p0_appcontainer_probe as identity
    import p0_sandbox_exec as sandbox
    import p0_sandbox_runtime as runtime
    import p0_tsp_evaluator as evaluator


ROOT = Path(__file__).resolve().parents[1]
PRIOR_RECORD = ROOT / "outputs" / "p0_task3_fixture_file_interface_01.jsonl"
FIXTURE_SOURCE = (b"import json,sys\n"
                  b"data=json.load(sys.stdin)\n"
                  b"print(json.dumps({'tour':list(range(len(data['coordinates'])))}))\n")


def _fixture_profiles() -> list[dict]:
    manifest, _ = sandbox.setup._manifest()
    names = ("P0Task3Probe_20261105_01", "P0Task3Probe_20261105_02")
    profiles = [identity._recorded_profile(identity.PROFILE_RECORDS[name]) for name in names]
    local = os.environ.get("LOCALAPPDATA")
    if not local or len({item["profile_sid"] for item in profiles}) != 2:
        raise ValueError("原测试身份不完整或不独立。")
    for slot, (name, profile) in enumerate(zip(names, profiles)):
        expected = Path(local) / "Packages" / name.lower() / "AC"
        folder = Path(profile["profile_folder"])
        if profile["profile_name"] != name or os.path.normcase(os.path.normpath(folder)) != os.path.normcase(os.path.normpath(expected)):
            raise ValueError("原测试身份与记录不一致。")
        for part in (folder.parent.parent, folder.parent, folder):
            runtime._safe_stat(part)
        runtime._verify_copied(folder / identity.RUNTIME_DIR, manifest)
        claim = ROOT / "outputs" / "p0_identity_claims" / f"{name}.json"
        source = folder / "p0_candidate" / "solver.py"
        for path in (claim.parent, claim, source.parent, source):
            runtime._safe_stat(path)
        expected = {"profile_name": name, "slot": slot, "phase": "build" if slot == 0 else "solve",
                    "source_sha256": hashlib.sha256(FIXTURE_SOURCE).hexdigest()}
        if json.loads(claim.read_text(encoding="utf-8")) != expected or source.read_bytes() != FIXTURE_SOURCE:
            raise ValueError("原测试文件或身份记录与固定样例不一致。")
    return profiles


def run_probe(save, record_name: str) -> dict:
    # 此探针只运行固定手写样例，故只要求受限执行探针通过。
    plan = sandbox._require_probe_gate()
    profiles = _fixture_profiles()
    previous = sandbox._read_events(PRIOR_RECORD)
    if (len(previous) != 4 or previous[0].get("event") != "sources"
            or previous[-1].get("event") != "result"
            or previous[-1].get("result", {}).get("evaluation") != {"valid": True, "objective": 4.0}
            or previous[-1].get("result", {}).get("passed") is not True):
        raise ValueError("原文件式探针记录不完整。")
    for slot, (event, profile) in enumerate(zip(previous[1:3], profiles)):
        source = Path(profile["profile_folder"]) / "p0_candidate" / "solver.py"
        claim = ROOT / "outputs" / "p0_identity_claims" / f"{profile['profile_name']}.json"
        result = event.get("result", {})
        if (event.get("event") != "probe" or event.get("case") != ("build" if slot == 0 else "solve")
                or result.get("profile_name") != profile["profile_name"]
                or Path(result.get("source_path", "")) != source or Path(result.get("identity_claim", "")) != claim
                or result.get("source_sha256") != hashlib.sha256(FIXTURE_SOURCE).hexdigest()
                or result.get("reason") != "exited" or result.get("exit_code") != 0):
            raise ValueError("原文件式探针来源不匹配。")

    coordinates = [[0, 0], [1, 0], [1, 1], [0, 1]]
    payload = json.dumps(evaluator.make_solver_input(coordinates, seed=0, time_limit_ms=15000)).encode("utf-8")
    lookup = {profile["profile_name"]: profile for profile in profiles}
    stem = Path(record_name).stem
    claim_dir = ROOT / "outputs" / (stem + "_claims")

    def fixed_test_profile(_plan, name):
        if name not in lookup:
            raise ValueError("只允许两个已授权的测试身份。")
        return lookup[name]

    def fixed_test_paths(_name, folder):
        return claim_dir, folder / stem / "solver.py"

    # 新建本次无害样例，完整执行资源门禁后的写入、只读锁、构建与求解。
    # 身份和路径限于已核验的两个旧测试身份，不占用16个新身份。
    with patch.object(sandbox, "_require_gate", return_value=plan), \
            patch.object(sandbox, "_profile", side_effect=fixed_test_profile), \
            patch.object(sandbox, "_candidate_paths", side_effect=fixed_test_paths):
        built = sandbox.run_candidate(profiles[0]["profile_name"], 0, FIXTURE_SOURCE, b"", build=True)
        save({"event": "probe", "case": "build", "result": built})
        solved = sandbox.run_candidate(profiles[1]["profile_name"], 1, FIXTURE_SOURCE, payload, build=False)
        save({"event": "probe", "case": "solve", "result": solved})
    if built["reason"] != "exited" or built["exit_code"] != 0:
        raise OSError("手写样例的文件式构建失败。")
    if solved["reason"] != "exited":
        raise OSError("手写样例的文件式求解未正常退出。")
    checked = evaluator.evaluate_response(coordinates, base64.b64decode(solved["stdout_b64"], validate=True),
                                          exit_code=solved["exit_code"], elapsed_ms=solved["elapsed_seconds"] * 1000,
                                          time_limit_ms=15000)
    return {"passed": checked == {"valid": True, "objective": 4.0}, "evaluation": checked,
            "source_sha256": hashlib.sha256(FIXTURE_SOURCE).hexdigest(),
            "prior_record_sha256": hashlib.sha256(PRIOR_RECORD.read_bytes()).hexdigest(),
            "scope": "仅在两个原测试身份中新增固定手写样例；不运行模型候选。"}


def main() -> int:
    parser = argparse.ArgumentParser(description="验证P0真实文件入口，只使用固定无害样例。")
    parser.add_argument("--record", required=True, help="outputs中新建 p0_task3_fixture_*.jsonl")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_fixture_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名无效。")
    with (ROOT / "outputs" / options.record).open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        save({"event": "sources", "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "executor_sha256": hashlib.sha256(Path(sandbox.__file__).read_bytes()).hexdigest()})
        try:
            result = run_probe(save, options.record)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
