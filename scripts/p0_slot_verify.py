"""以16个已记录的不同身份运行固定无害探针，不接受候选程序。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import threading
import time

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


def _profiles(plan: dict) -> list[dict]:
    if plan != setup.build_plan():
        raise ValueError("身份准备清单已改变。")
    records = {}
    plan_digest = hashlib.sha256(setup.PLAN.read_bytes()).hexdigest()
    for target in plan["targets"]:
        setup._check_plan_provenance(Path(target["profile_record"]), plan_digest)
        records[target["name"]] = Path(target["profile_record"]).name
    if len(records) != 16:
        raise ValueError("需要16个不同的身份记录。")
    profiles = [identity._recorded_profile(record) for record in records.values()]
    if (len({item["profile_name"] for item in profiles}) != 16
            or len({item["profile_sid"] for item in profiles}) != 16):
        raise ValueError("身份或SID不独立。")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA。")
    manifest, _ = setup._manifest()
    for profile in profiles:
        expected = Path(local) / "Packages" / profile["profile_name"].lower() / "AC"
        folder = Path(profile["profile_folder"])
        if os.path.normcase(os.path.normpath(folder)) != os.path.normcase(os.path.normpath(expected)):
            raise ValueError("身份目录与记录不一致。")
        for path in (folder.parent.parent, folder.parent, folder):
            runtime._safe_stat(path)
        runtime._verify_copied(folder / identity.RUNTIME_DIR, manifest)
    if identity.BOUNDARY_FIXTURE.read_text(encoding="utf-8") != "P0 simulated sensitive data; not a real secret.\n":
        raise ValueError("宿主模拟文件与预期不一致。")
    identity.PROFILE_RECORDS.update(records)  # 仅在本次验证进程内扩展允许的测试身份。
    return profiles


def _round(profiles: list[dict], slots: list[dict], mode: str, save, port=None, address=None) -> list[dict]:
    def run_one(index):
        result = restricted._run_fixed(profiles[index], profiles[(index + 1) % 16], slots[index], mode,
                                       port=port, network_address=address)
        result["profile_name"] = profiles[index]["profile_name"]
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(run_one, range(16)))
    for item in results:
        save({"event": "probe", "result": item})
    return results


def _parallel_passed(results: list[dict]) -> bool:
    try:
        return (len(results) == 16 and len({item["profile_name"] for item in results}) == 16
                and len({item["pid"] for item in results}) == 16
                and len({item["logical_processor"] for item in results}) == 16
                and all(item["reason"] == "exited" and item["exit_code"] == 0
                        and json.loads(restricted._stdout(item)) ==
                        {"pid": item["pid"], "affinity": 1 << item["logical_processor"]} for item in results)
                and max(item["resumed_monotonic"] for item in results) <
                min(item["finished_monotonic"] for item in results))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _network_all(profiles: list[dict], slots: list[dict], address: str, save) -> dict:
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
                except OSError as exc:
                    if not stop.is_set():
                        errors.append(type(exc).__name__)
                    return
                with connection:
                    connections.append(True)

        server = threading.Thread(target=serve, daemon=True)
        server.start()
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
            server.join(timeout=3)
            if server.is_alive():
                errors.append("server_not_stopped")
    try:
        blocked = (len(results) == 16 and all(item["reason"] == "exited" and item["exit_code"] == 0
                   and json.loads(restricted._stdout(item)).get("connected") is False for item in results))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        blocked = False
    return {"address": address, "passed": blocked and (before, after, final) == (1, 1, 2) and not errors,
            "host_connection_counts": [before, after, final], "server_errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="验证16个已准备的测试身份。")
    parser.add_argument("--record", required=True, help="outputs 中新建 p0_task3_slots_verify_*.jsonl")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_slots_verify_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名无效。")
    with (ROOT / "outputs" / options.record).open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        sources = [Path(__file__), Path(setup.__file__), Path(restricted.__file__), Path(identity.__file__),
                   Path(job.__file__), Path(runtime.__file__)]
        save({"event": "sources", "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                                for path in sources}})
        result = {"passed": False, "scope": "只验证16个不同身份的固定无害进程。"}
        try:
            result["resource_precheck"] = job._resource_gate()
            plan = json.loads(setup.PLAN.read_text(encoding="utf-8"))
            profiles = _profiles(plan)
            slots = job.select_mapping(*job.read_windows_topology())["workers"]
            holds = _round(profiles, slots, "hold", save)
            result["parallel_passed"] = _parallel_passed(holds)
            if not result["parallel_passed"]:
                raise OSError("16身份并行和绑核未通过。")
            file_checks = {}
            for mode, expected in (("read_own_runtime", "read"), ("read_other_runtime", "denied"),
                                   ("read_host", "denied")):
                checks = _round(profiles, slots, mode, save)
                file_checks[mode] = sum(restricted._read_result(item, expected) for item in checks)
            result["file_checks"] = file_checks
            if any(count != 16 for count in file_checks.values()):
                raise OSError("16身份模拟文件检查未通过。")
            addresses = restricted._local_private_ipv4()
            if not addresses:
                raise OSError("没有可核验的本机局域网地址。")
            result["network_checks"] = [_network_all(profiles, slots, "127.0.0.1", save),
                                        _network_all(profiles, slots, addresses[0], save)]
            result["passed"] = all(item["passed"] for item in result["network_checks"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
