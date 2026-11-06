"""P0 任务4：真实生成单文件 TSP 程序，并以独立评价器检查首批实例。"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

if __package__:
    from . import p0_cpu_topology as topology
    from . import p0_model_runtime as model
    from . import p0_sandbox_exec as sandbox
    from . import p0_tsp_evaluator as evaluator
else:
    import p0_cpu_topology as topology
    import p0_model_runtime as model
    import p0_sandbox_exec as sandbox
    import p0_tsp_evaluator as evaluator


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "outputs" / "p0_task4"
SCHEMA = ROOT / "cfg" / "p0_model_response.schema.json"
MAX_CALLS = 3
MAX_TOKENS = 150_000
MAX_CPU_SECONDS = 1_200
MAX_WALL_SECONDS = 3_600
SOLVE_LIMIT_MS = 15_000
PROMPT = """Design one complete Python program for the symmetric Euclidean traveling salesman problem.
Use only the Python 3.13 standard library. The program must read one UTF-8 JSON object from stdin,
with keys coordinates (a list of [x,y] finite numeric points), seed (a nonnegative integer), and
time_limit_ms (a positive integer). It must print exactly one JSON object to stdout with a key
tour containing every city index exactly once, without repeating the starting city. The objective
is the closed-tour Euclidean distance, minimized; it is calculated independently by the evaluator.
The program may use a single mechanism. Favor a simple, reliable solution and finish well before
time_limit_ms, including input and initialization. Avoid extra stdout output, files, network,
external packages, and child processes. Preserve a valid complete tour even under a time limit.
Return the requested JSON object containing a concise thought and complete runnable code.
Do not use tools or read files; respond only with the requested output.
"""


class StopRun(RuntimeError):
    """预算、隔离、模型事件或输入无法满足已确定的合同。"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        with path.open("x", encoding="utf-8"):
            pass

    def add(self, event: str, **fields) -> None:
        row = {"event": event, "at_utc": now(), **fields}
        with self.lock, self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()


class BatchGuard:
    """阻止同一项目的多个任务4批次同时启动模型调用。"""

    def __enter__(self):
        self.kernel, _ = sandbox.job._apis()
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        self.kernel.ReleaseMutex.restype = wintypes.BOOL
        self.handle = self.kernel.CreateMutexW(None, False, "Local\\P0AgenticHybridTask4Batch")
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if self.kernel.WaitForSingleObject(self.handle, 0) not in (0, 0x80):
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            raise StopRun("已有任务4批次运行，不能重复启动。")
        return self

    def __exit__(self, _kind, _value, _traceback):
        if self.handle:
            self.kernel.ReleaseMutex(self.handle)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _new_batch() -> Path:
    RUNS.mkdir(exist_ok=True)
    for path in sorted(RUNS.glob("batch_*/events.jsonl")):
        try:
            records = [json.loads(line) for line in path.read_bytes().splitlines()]
        except (OSError, ValueError) as exc:
            raise StopRun("已有批次记录无法核验，不能重置预算。") from exc
        if any(type(row) is not dict for row in records):
            raise StopRun("已有批次记录格式无效，不能重置预算。")
        if any(row.get("event") == "model_attempt_started" for row in records):
            raise StopRun(f"已有批次发起过模型调用；须检查既有记录，不能重置预算：{path}")
    for index in range(1, 1000):
        batch = RUNS / f"batch_{index:02d}"
        try:
            batch.mkdir()
            return batch
        except FileExistsError:
            continue
    raise StopRun("无法创建不覆盖旧记录的新批次。")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fresh_profiles(plan: dict) -> list[str]:
    fresh = []
    for target in plan["targets"]:
        name = target["name"]
        folder = Path(target["profile_dir"])
        claim = ROOT / "outputs" / "p0_identity_claims" / f"{name}.json"
        if not claim.exists() and not (folder / "p0_candidate").exists():
            fresh.append(name)
    return fresh


def _instances() -> tuple[dict, list[tuple[dict, list]], dict]:
    cores, cpu_sets, process_mask, system_mask = topology.read_windows_topology()
    mapping = topology.select_mapping(cores, cpu_sets, process_mask, system_mask)
    instances = [(item, evaluator.load_instance(item["instance_id"])) for item in mapping["instances"]]
    if len(instances) != 15:
        raise StopRun("首批实例数量与合同不一致。")
    return mapping, instances, {"process_mask": process_mask, "system_mask": system_mask}


def _stable_mapping(mapping: dict) -> dict:
    return {**mapping, "workers": [{key: value for key, value in worker.items() if key != "parked"}
                                    for worker in mapping["workers"]]}


def _remaining(deadline: float, required: float = 0) -> None:
    if time.monotonic() + required >= deadline:
        raise StopRun("本批墙钟余额不足，停止新作业。")


def _tokens(usage: dict) -> int:
    return usage["input_tokens"] + usage["output_tokens"]


def _evaluate(coordinates: list, result: dict) -> dict:
    if result.get("reason") != "exited":
        return {"valid": False, "code": str(result.get("reason", "unknown"))}
    try:
        stdout = base64.b64decode(result["stdout_b64"], validate=True)
        return evaluator.evaluate_response(coordinates, stdout, exit_code=result["exit_code"],
                                           elapsed_ms=result["elapsed_seconds"] * 1000,
                                           time_limit_ms=SOLVE_LIMIT_MS)
    except evaluator.EvaluationError as exc:
        return {"valid": False, "code": exc.code, "message": str(exc)}
    except (ValueError, KeyError, TypeError) as exc:
        raise StopRun("可信执行结果格式无效。") from exc


def _candidate(profile: str, slot: int, source: bytes, payload: bytes, *, build: bool,
               deadline: float, ledger: Ledger) -> dict:
    while True:
        _remaining(deadline, 60 if not build else 45)
        try:
            return sandbox.run_candidate(profile, slot, source, payload, build=build)
        except OSError as exc:
            # 资源不足发生在身份登记之前，可以等待后重试；其他异常停止。
            if not ("资源检查不满足 P0 条件" in str(exc) or "可用内存低于 16 GiB" in str(exc)):
                raise
            ledger.add("resource_wait", profile=profile, slot=slot, reason=str(exc))
            time.sleep(5)


def _model_response(batch: Path, binary: Path, deadline: float, ledger: Ledger) -> tuple[bytes, dict, int]:
    total = 0
    for attempt in range(1, MAX_CALLS + 1):
        _remaining(deadline, 60)
        directory = batch / f"attempt_{attempt:02d}"
        directory.mkdir()
        prompt = PROMPT if attempt == 1 else PROMPT + "\nThe previous response did not match the requested JSON format. Correct the format.\n"
        with (directory / "request.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(prompt)
        audit = model.EventAudit()
        command = model.command(binary, directory, SCHEMA)
        ledger.add("model_attempt_started", attempt=attempt, model=model.MODEL,
                   request_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        print(f"模型调用 {attempt}/{MAX_CALLS} 已启动。", flush=True)
        result = model.limited_process(command, directory / "model_events.jsonl", directory / "model_stderr.txt",
                                       stdin=prompt.encode("utf-8"), deadline=deadline, audit=audit)
        write_json(directory / "model_process.json", {"command": command, **result})
        if result["reason"] != "exited" or result["exit_code"] != 0:
            ledger.add("model_stopped", attempt=attempt, process=result, usage="unknown")
            raise StopRun("模型进程失败或产生非预期事件，调用用量无法完整确认。")
        try:
            response, usage = audit.finish()
        except model.ResponseFormatError as exc:
            total += _tokens(exc.usage)
            ledger.add("model_format_error", attempt=attempt, usage=exc.usage,
                       total_reported_tokens=total, reason=str(exc))
            if total >= MAX_TOKENS or attempt == MAX_CALLS:
                raise StopRun("模型响应格式失败或已达到 token / 调用上限。") from exc
            continue
        except model.ModelError as exc:
            ledger.add("model_stopped", attempt=attempt, usage="unknown", reason=str(exc))
            raise StopRun("模型事件或用量无法核实。") from exc
        total += _tokens(usage)
        write_json(directory / "response.json", response)
        source = response["code"].encode("utf-8")
        if not source or len(source) > sandbox.MAX_SOURCE_BYTES:
            ledger.add("model_stopped", attempt=attempt, usage=usage, reason="source_limit")
            raise StopRun("生成的源码超过合同上限。")
        with (directory / "solver.py").open("xb") as stream:
            stream.write(source)
        ledger.add("model_completed", attempt=attempt, usage=usage, total_reported_tokens=total,
                   source_sha256=hashlib.sha256(source).hexdigest())
        if total >= MAX_TOKENS:
            raise StopRun("已达到 token 上限，停止后续构建和求解。")
        return source, {"attempt": attempt, "usage": usage, "total_reported_tokens": total}, attempt
    raise StopRun("模型调用上限已用完。")


def _run_panel(directory: Path, source: bytes, profiles: list[str], instances: list[tuple[dict, list]],
               deadline: float, ledger: Ledger) -> list[dict]:
    cases = directory / "instances"
    cases.mkdir()

    def worker(index: int) -> dict:
        item, coordinates = instances[index]
        case = cases / item["instance_id"]
        case.mkdir()
        input_value = evaluator.make_solver_input(coordinates, seed=0, time_limit_ms=SOLVE_LIMIT_MS)
        payload = json.dumps(input_value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        with (case / "input.json").open("xb") as stream:
            stream.write(payload)
        try:
            process = _candidate(profiles[index], item["slot"], source, payload, build=False,
                                 deadline=deadline, ledger=ledger)
            checked = _evaluate(coordinates, process)
            result = {"instance_id": item["instance_id"], "seed": 0, "slot": item["slot"],
                      "logical_processor": item["logical_processor"], "process": process, "evaluation": checked}
        except (OSError, ValueError, StopRun) as exc:
            result = {"instance_id": item["instance_id"], "seed": 0, "slot": item["slot"],
                      "error": f"{type(exc).__name__}: {exc}", "evaluation": {"valid": False},
                      "cpu_accounting": "unknown"}
        write_json(case / "result.json", result)
        ledger.add("instance_finished", instance_id=item["instance_id"], valid=result["evaluation"]["valid"])
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        futures = [pool.submit(worker, index) for index in range(15)]
        return [future.result() for future in futures]


def _run_locked() -> dict:
    plan = sandbox._require_gate()
    mapping, instances, masks = _instances()
    profiles = _fresh_profiles(plan)
    if len(profiles) < 16:
        raise StopRun("不足16个未分配身份，无法完成一次构建和15个求解作业。")
    for name in profiles[:16]:
        sandbox._profile(plan, name)
    batch = _new_batch()
    ledger = Ledger(batch / "events.jsonl")
    cpu_start = time.process_time()
    child_cpu = 0.0
    try:
        preflight_dir = batch / "preflight"
        preflight_dir.mkdir()
        checked = model.local_preflight(preflight_dir)
        checked["quota"] = model.quota(model.executable())
        checked["executable_sha256"] = _digest(model.executable())
        write_json(preflight_dir / "result.json", checked)
        ledger.add("preflight_passed", model=model.MODEL, version=model.VERSION,
                   fresh_profiles=len(profiles), quota=checked["quota"])
        snapshot = {"mapping": mapping, "affinity_masks": masks,
                    "instance_manifest_sha256": _digest(evaluator.DATA_DIR / "manifest.json"),
                    "dataset_sha256": {name: _digest(evaluator.DATA_DIR / name) for name in ("train50.json", "train200.json")},
                    "model_schema_sha256": _digest(SCHEMA), "executor_sha256": _digest(Path(sandbox.__file__)),
                    "limits": {"model_calls": MAX_CALLS, "reported_tokens": MAX_TOKENS,
                               "cpu_seconds": MAX_CPU_SECONDS, "wall_seconds": MAX_WALL_SECONDS,
                               "solve_time_ms": SOLVE_LIMIT_MS}}
        write_json(batch / "contract.json", snapshot)
        started_at = datetime.now(timezone.utc)
        deadline = time.monotonic() + MAX_WALL_SECONDS
        freeze_deadline = started_at + timedelta(seconds=MAX_WALL_SECONDS)
        ledger.add("generation_clock_started", wall_limit_seconds=MAX_WALL_SECONDS,
                   freeze_deadline_utc=freeze_deadline.isoformat())
        source, model_result, attempt = _model_response(batch, model.executable(), deadline, ledger)
        current_mapping, current_instances, current_masks = _instances()
        if (_stable_mapping(current_mapping) != _stable_mapping(mapping) or current_masks != masks
                or [item[0] for item in current_instances] != [item[0] for item in instances]):
            raise StopRun("实例或核映射发生变化。")
        if (_digest(evaluator.DATA_DIR / "manifest.json") != snapshot["instance_manifest_sha256"]
                or any(_digest(evaluator.DATA_DIR / name) != digest for name, digest in snapshot["dataset_sha256"].items())):
            raise StopRun("实例清单或数据文件发生变化。")
        directory = batch / f"attempt_{attempt:02d}"
        _remaining(deadline, 45)
        print("模型源码已保存，开始受限构建。", flush=True)
        build = _candidate(profiles[0], 15, source, b"", build=True, deadline=deadline, ledger=ledger)
        write_json(directory / "build.json", build)
        child_cpu += build["cpu_seconds"]
        ledger.add("build_finished", attempt=attempt, reason=build["reason"], exit_code=build["exit_code"])
        if build["reason"] != "exited" or build["exit_code"] != 0:
            raise StopRun("受限构建失败；当前身份不足以再次构建并完成15个实例。")
        if child_cpu + (time.process_time() - cpu_start) + 230 >= MAX_CPU_SECONDS:
            raise StopRun("CPU 余额不足以启动完整实例面板。")
        _remaining(deadline, 60)
        print("受限构建通过，开始15实例独立评价。", flush=True)
        panel = _run_panel(directory, source, profiles[1:16], current_instances, deadline, ledger)
        write_json(directory / "panel.json", panel)
        child_cpu += sum(row["process"]["cpu_seconds"] for row in panel if "process" in row)
        if any("cpu_accounting" in row for row in panel):
            raise StopRun("至少一个求解作业的 CPU 实耗无法确认。")
        cpu_used = child_cpu + (time.process_time() - cpu_start)
        valid = sum(row["evaluation"]["valid"] is True for row in panel)
        summary = {"status": "passed" if valid == 15 and cpu_used < MAX_CPU_SECONDS and time.monotonic() < deadline else "failed",
                   "attempt": attempt, "model": model_result, "instances": len(panel), "valid_instances": valid,
                   "cpu_seconds": cpu_used, "cpu_scope": "构建和求解作业 CPU，加宿主进程本批 CPU；包含部分保守计入的准备开销。",
                   "wall_seconds_remaining": max(0, deadline - time.monotonic()),
                   "freeze_deadline_utc": freeze_deadline.isoformat(), "batch": str(batch),
                   "source_sha256": hashlib.sha256(source).hexdigest(), "frozen_run_completed": False}
        write_json(batch / "summary.json", summary)
        ledger.add("task4_finished", **summary)
        return summary
    except (OSError, ValueError, KeyError, TypeError, model.ModelError, StopRun) as exc:
        failure = {"status": "failed", "error": f"{type(exc).__name__}: {exc}",
                   "known_cpu_seconds": child_cpu + (time.process_time() - cpu_start)}
        failure["batch"] = str(batch)
        write_json(batch / "failure.json", failure)
        ledger.add("task4_stopped", **failure)
        return failure


def run() -> dict:
    with BatchGuard():
        return _run_locked()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True, help="执行唯一的P0任务4批次")
    parser.parse_args()
    try:
        result = run()
    except (OSError, ValueError, KeyError, TypeError, model.ModelError, StopRun) as exc:
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
