"""冻结P0已评价程序，核验新身份并在无模型服务依赖下重跑。"""

from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_restricted_probe as probe
    from . import p0_sandbox_exec as sandbox
    from . import p0_sandbox_runtime as runtime
    from . import p0_slot_setup as setup
    from . import p0_task4 as task4
    from . import p0_task5_profiles as profiles_setup
    from . import p0_tsp_evaluator as evaluator
else:
    import p0_appcontainer_probe as identity
    import p0_restricted_probe as probe
    import p0_sandbox_exec as sandbox
    import p0_sandbox_runtime as runtime
    import p0_slot_setup as setup
    import p0_task4 as task4
    import p0_task5_profiles as profiles_setup
    import p0_tsp_evaluator as evaluator


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "outputs" / "p0_task4" / "batch_01"
BATCH = ROOT / "outputs" / "p0_task5" / "batch_01"
FROZEN = BATCH / "frozen"
VERIFY = ROOT / "outputs" / "p0_task5_profile_verify_20261106_01.jsonl"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _copy_new(source: Path, target: Path) -> str:
    data = source.read_bytes()
    with target.open("xb") as stream:
        stream.write(data)
    digest = hashlib.sha256(data).hexdigest()
    if sha(target) != digest:
        raise OSError("冻结文件摘要不一致。")
    return digest


def _remaining() -> float:
    prior = json.loads((PRIOR / "summary.json").read_text(encoding="utf-8"))
    deadline = datetime.fromisoformat(prior["freeze_deadline_utc"])
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        raise task4.StopRun("本批60分钟墙钟预算已到期，不能执行冻结重跑。")
    return remaining


def freeze() -> dict:
    _remaining()
    sandbox._require_gate()
    prior = json.loads((PRIOR / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads((PRIOR / "independent_audit.json").read_text(encoding="utf-8"))
    panel = json.loads((PRIOR / "attempt_01" / "panel.json").read_text(encoding="utf-8"))
    source = PRIOR / "attempt_01" / "solver.py"
    if (prior.get("status") != "passed" or prior.get("valid_instances") != 15
            or not audit.get("passed") or len(panel) != 15
            or any(row.get("evaluation", {}).get("valid") is not True for row in panel)
            or sha(source) != prior.get("source_sha256") or audit.get("source_sha256") != sha(source)):
        raise ValueError("任务4的评价证据或源码摘要不一致。")
    BATCH.parent.mkdir(exist_ok=True)
    BATCH.mkdir()
    FROZEN.mkdir()
    paths = {
        "solver.py": source,
        "runtime_manifest.json": runtime.MANIFEST,
        "run_contract.json": PRIOR / "contract.json",
        "build_record.json": PRIOR / "attempt_01" / "build.json",
        "task4_summary.json": PRIOR / "summary.json",
        "task4_audit.json": PRIOR / "independent_audit.json",
    }
    files = {name: _copy_new(path, FROZEN / name) for name, path in paths.items()}
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "source_task4": str(PRIOR),
                "files_sha256": files, "python_version": "3.13.12", "interface": "python -I -B solver.py",
                "build": "语法编译检查，无独立编译二进制产物。",
                "model_service": "求解时仅用本地标准库和标准输入，不调用模型。",
                "freeze_deadline_utc": prior["freeze_deadline_utc"]}
    _write_json(FROZEN / "manifest.json", manifest)
    return {"passed": True, "frozen_dir": str(FROZEN), "manifest_sha256": sha(FROZEN / "manifest.json"),
            "source_sha256": files["solver.py"], "remaining_seconds": _remaining()}


def _frozen() -> tuple[dict, bytes]:
    manifest = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
    expected = {"solver.py", "runtime_manifest.json", "run_contract.json", "build_record.json",
                "task4_summary.json", "task4_audit.json"}
    if set(manifest.get("files_sha256", {})) != expected:
        raise ValueError("冻结清单不完整。")
    for name, digest in manifest["files_sha256"].items():
        if sha(FROZEN / name) != digest:
            raise ValueError(f"冻结文件发生变化：{name}")
    if (sha(FROZEN / "runtime_manifest.json") != sha(runtime.MANIFEST)
            or manifest.get("freeze_deadline_utc") != json.loads((PRIOR / "summary.json").read_text(encoding="utf-8"))["freeze_deadline_utc"]):
        raise ValueError("运行时或截止时间与冻结合同不一致。")
    return manifest, (FROZEN / "solver.py").read_bytes()


def _profiles() -> list[dict]:
    plan = json.loads(profiles_setup.PLAN.read_text(encoding="utf-8"))
    if plan != profiles_setup.build_plan():
        raise ValueError("任务5身份准备清单或脚本已变化。")
    plan_digest = sha(profiles_setup.PLAN)
    manifest, _ = setup._manifest()
    found = []
    records = {}
    for target in plan["targets"]:
        name = target["name"]
        record = Path(target["profile_record"])
        setup._check_plan_provenance(record, plan_digest)
        profile = identity._recorded_profile(record.name)
        if (profile["profile_name"] != name
                or os.path.normcase(os.path.normpath(profile["profile_folder"])) != os.path.normcase(os.path.normpath(target["profile_dir"]))):
            raise ValueError("任务5身份与清单不一致。")
        folder = Path(profile["profile_folder"])
        for part in (folder.parent.parent, folder.parent, folder):
            runtime._safe_stat(part)
        runtime._verify_copied(folder / identity.RUNTIME_DIR, manifest)
        if (folder / "p0_frozen_solver").exists() or (ROOT / "outputs" / "p0_task5_identity_claims" / f"{name}.json").exists():
            raise FileExistsError("身份已分配，不能复用或覆盖。")
        records[name] = record.name
        found.append(profile)
    if len(found) != 15 or len({item["profile_sid"] for item in found}) != 15:
        raise ValueError("任务5须使用15个不同身份。")
    identity.PROFILE_RECORDS.update(records)
    return found


def _round(profiles: list[dict], slots: list[dict], mode: str, save, *, port=None, address=None) -> list[dict]:
    def run(index):
        result = probe._run_fixed(profiles[index], profiles[(index + 1) % 15], slots[index], mode,
                                  port=port, network_address=address)
        result["profile_name"] = profiles[index]["profile_name"]
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        results = list(pool.map(run, range(15)))
    for item in results:
        save({"event": "probe", "case": mode, "result": item})
    return results


def _network(profiles: list[dict], slots: list[dict], address: str, save) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((address, 0))
        listener.listen(20)
        listener.settimeout(0.2)
        port = listener.getsockname()[1]
        connections, errors = [], []
        stop = threading.Event()

        def serve():
            while not stop.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if not stop.is_set():
                        errors.append("listener_error")
                    break
                with connection:
                    connections.append(True)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(connections) < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            before = len(connections)
            mode = "loopback" if address == "127.0.0.1" else "local_network"
            results = _round(profiles, slots, mode, save, port=port, address=address)
            time.sleep(0.25)
            after = len(connections)
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(connections) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            final = len(connections)
        finally:
            stop.set()
            thread.join(timeout=3)
            if thread.is_alive():
                errors.append("listener_not_stopped")
    blocked = all(item["reason"] == "exited" and item["exit_code"] == 0
                  and json.loads(probe._stdout(item)).get("connected") is False for item in results)
    return {"address": address, "passed": len(results) == 15 and blocked and (before, after, final) == (1, 1, 2)
            and not errors, "host_connection_counts": [before, after, final], "errors": errors}


def verify_profiles() -> dict:
    _remaining()
    sandbox._require_gate()
    _frozen()
    with VERIFY.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        save({"event": "sources", "script_sha256": sha(Path(__file__)), "plan_sha256": sha(profiles_setup.PLAN),
              "executor_sha256": sha(Path(sandbox.__file__)), "frozen_manifest_sha256": sha(FROZEN / "manifest.json")})
        try:
            profiles = _profiles()
            slots = task4.topology.select_mapping(*task4.topology.read_windows_topology())["workers"][:15]
            holds = _round(profiles, slots, "hold", save)
            parallel = (len({item["pid"] for item in holds}) == 15
                        and len({item["logical_processor"] for item in holds}) == 15
                        and all(item["reason"] == "exited" and item["exit_code"] == 0
                                and json.loads(probe._stdout(item)) == {"pid": item["pid"], "affinity": 1 << item["logical_processor"]}
                                for item in holds)
                        and max(item["resumed_monotonic"] for item in holds) < min(item["finished_monotonic"] for item in holds))
            if not parallel:
                raise OSError("15身份并发或绑核检查失败。")
            files = {}
            for mode, expected in (("read_own_runtime", "read"), ("read_other_runtime", "denied"), ("read_host", "denied")):
                files[mode] = sum(probe._read_result(item, expected) for item in _round(profiles, slots, mode, save))
            if any(value != 15 for value in files.values()):
                raise OSError("15身份文件边界检查失败。")
            addresses = probe._local_private_ipv4()
            if not addresses:
                raise OSError("缺少可检查的本机局域网地址。")
            networks = [_network(profiles, slots, "127.0.0.1", save), _network(profiles, slots, addresses[0], save)]
            result = {"passed": all(item["passed"] for item in networks), "parallel_passed": parallel,
                      "file_checks": files, "network_checks": networks,
                      "scope": "固定无害进程；仅证明记录中的文件路径和网络地址。"}
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    return result


def _verification_gate() -> None:
    events = sandbox._read_events(VERIFY)
    first, last = events[0], events[-1]
    if (first.get("event") != "sources" or first.get("script_sha256") != sha(Path(__file__))
            or first.get("plan_sha256") != sha(profiles_setup.PLAN)
            or first.get("executor_sha256") != sha(Path(sandbox.__file__))
            or first.get("frozen_manifest_sha256") != sha(FROZEN / "manifest.json")
            or last.get("event") != "result" or last.get("result", {}).get("passed") is not True):
        raise ValueError("任务5身份隔离验收记录不匹配。")


def _solve(profile: dict, slot: dict, source: bytes, payload: bytes) -> dict:
    folder = Path(profile["profile_folder"])
    destination = folder / "p0_frozen_solver"
    source_path = destination / "solver.py"
    claims = ROOT / "outputs" / "p0_task5_identity_claims"
    claim_path = claims / (profile["profile_name"] + ".json")
    expected = hashlib.sha256(source).hexdigest()

    def prepare():
        claims.mkdir(exist_ok=True)
        runtime._safe_stat(claims)
        with claim_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"profile_name": profile["profile_name"], "slot": slot["slot"],
                       "phase": "frozen_solve", "source_sha256": expected}, stream)
            stream.write("\n")
        destination.mkdir()
        runtime._safe_stat(destination)
        with source_path.open("xb") as stream:
            stream.write(source)
        lock = sandbox._LockedSource(source_path)
        lock.__enter__()
        try:
            if sha(source_path) != expected:
                raise OSError("冻结源码写入后摘要不一致。")
        except BaseException:
            lock.__exit__(None, None, None)
            raise
        return lock

    while True:
        if _remaining() < 30:
            raise task4.StopRun("剩余墙钟不足以启动冻结求解作业。")
        try:
            with sandbox._SlotGuard(slot["slot"]):
                result = sandbox._run_program(profile, slot, source_path, payload, build=False,
                                              prepare_source=prepare, expected_source_sha=expected)
            break
        except OSError as exc:
            if not ("资源检查不满足 P0 条件" in str(exc) or "可用内存低于 16 GiB" in str(exc)):
                raise
            time.sleep(5)
    result.update({"profile_name": profile["profile_name"], "source_path": str(source_path),
                   "identity_claim": str(claim_path), "source_sha256": expected})
    return result


def run() -> dict:
    with task4.BatchGuard():
        if _remaining() < 60:
            raise task4.StopRun("剩余墙钟不足以启动完整冻结重跑。")
        sandbox._require_gate()
        manifest, source = _frozen()
        _verification_gate()
        profiles = _profiles()
        if _remaining() < 60:
            raise task4.StopRun("剩余墙钟不足以启动完整冻结重跑。")
        mapping, instances, masks = task4._instances()
        contract = json.loads((FROZEN / "run_contract.json").read_text(encoding="utf-8"))
        if (task4._stable_mapping(mapping) != task4._stable_mapping(contract["mapping"])
                or masks != contract["affinity_masks"]
                or sha(evaluator.DATA_DIR / "manifest.json") != contract["instance_manifest_sha256"]
                or any(sha(evaluator.DATA_DIR / name) != digest for name, digest in contract["dataset_sha256"].items())):
            raise ValueError("实例或核映射与冻结合同不一致。")
        case_dir = BATCH / "instances"
        case_dir.mkdir()
        cpu_start = time.process_time()

        def worker(index):
            item, coordinates = instances[index]
            folder = case_dir / item["instance_id"]
            folder.mkdir()
            input_value = evaluator.make_solver_input(coordinates, seed=0, time_limit_ms=15000)
            payload = json.dumps(input_value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            with (folder / "input.json").open("xb") as stream:
                stream.write(payload)
            try:
                result = _solve(profiles[index], mapping["workers"][item["slot"]], source, payload)
                checked = task4._evaluate(coordinates, result)
                row = {"instance_id": item["instance_id"], "seed": 0, "slot": item["slot"],
                       "logical_processor": item["logical_processor"], "process": result, "evaluation": checked}
            except (OSError, ValueError, task4.StopRun) as exc:
                row = {"instance_id": item["instance_id"], "error": f"{type(exc).__name__}: {exc}",
                       "evaluation": {"valid": False}, "cpu_accounting": "unknown"}
            _write_json(folder / "result.json", row)
            print(f"冻结实例 {item['instance_id']}：{row['evaluation']['valid']}", flush=True)
            return row

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
            rows = list(pool.map(worker, range(15)))
        _write_json(BATCH / "panel.json", rows)
        if any("cpu_accounting" in row for row in rows):
            raise task4.StopRun("至少一个冻结作业的 CPU 实耗不可核实。")
        child_cpu = sum(row["process"]["cpu_seconds"] for row in rows)
        current_cpu = child_cpu + (time.process_time() - cpu_start)
        prior = json.loads((FROZEN / "task4_summary.json").read_text(encoding="utf-8"))
        total_cpu = current_cpu + prior["cpu_seconds"]
        remaining = _remaining()
        _frozen()
        valid = sum(row["evaluation"]["valid"] is True for row in rows)
        summary = {"status": "passed" if valid == 15 and total_cpu < 1200 and remaining > 0 else "failed",
                   "instances": 15, "valid_instances": valid, "frozen_solve_cpu_seconds": current_cpu,
                   "task4_and_task5_cpu_seconds": total_cpu, "remaining_wall_seconds": remaining,
                   "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                   "source_sha256": manifest["files_sha256"]["solver.py"],
                   "frozen_manifest_sha256": sha(FROZEN / "manifest.json"),
                   "model_service": "未调用模型；求解进程使用无网络能力身份和本地文件。"}
        _write_json(BATCH / "summary.json", summary)
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "verify-profiles", "run"))
    args = parser.parse_args()
    try:
        result = {"freeze": freeze, "verify-profiles": verify_profiles, "run": run}[args.mode]()
    except (OSError, ValueError, KeyError, TypeError, task4.StopRun) as exc:
        result = {"passed": False, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    return 0 if result.get("passed") is True or result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
