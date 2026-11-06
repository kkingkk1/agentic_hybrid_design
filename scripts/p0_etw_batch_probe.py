"""准备16个自建线程探针和两个PID负载过滤会话；不得执行候选。"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import threading
import time
import uuid

if __package__:
    from . import p0_etw_pid_probe as etw
    from . import p0_job_probe as job
    from .p0_cpu_topology import read_windows_topology, select_mapping
else:
    import p0_etw_pid_probe as etw
    import p0_job_probe as job
    from p0_cpu_topology import read_windows_topology, select_mapping


ROOT = Path(__file__).resolve().parents[1]


def _partitions(pids: list[int]) -> list[list[int]]:
    if (type(pids) is not list or len(pids) != 16
            or any(type(pid) is not int or not 0 < pid <= 0xFFFFFFFF for pid in pids)):
        raise ValueError("批量探针需要16个互异、有效的目标 PID。")
    if len(set(pids)) != 16:
        raise ValueError("批量探针需要16个互异、有效的目标 PID。")
    return [pids[:8], pids[8:]]


class _FilteredSession:
    def __init__(self, advapi, pids: list[int], control_id: uuid.UUID, failure: threading.Event, sink):
        self.advapi = advapi
        self.name = "P0Task3-" + uuid.uuid4().hex
        self.pids = set(pids)
        self.control_id = control_id
        self.failure = failure
        self.sink = sink
        self.trace = etw.U64()
        self.storage = etw.SessionBuffer()
        self.props = self.storage.properties
        self.props.wnode.size = ctypes.sizeof(self.storage)
        self.props.wnode.client, self.props.wnode.flags = 1, 0x00020000
        self.props.buffer_size, self.props.min_buffers, self.props.max_buffers = 64, 2, 4
        self.props.mode, self.props.flush_timer = 0x100, 1
        self.props.name_offset = ctypes.sizeof(etw.TraceProperties)
        self.consumer = None
        self.consumer_thread = None
        self.trace_status = []
        self.started = False
        self.tids = {pid: set() for pid in pids}
        self.result = {"session": self.name, "target_pids": pids, "control_events": 0,
                       "foreign_events": 0, "invalid_events": 0, "callback_errors": []}

        @etw.EventCallback
        def on_event(pointer):
            try:
                record = pointer.contents
                provider = bytes(record.header.provider.data)
                if provider == self.control_id.bytes_le and record.header.descriptor.id == 77:
                    self.result["control_events"] += 1
                elif provider == etw.KERNEL_PROCESS.bytes_le:
                    if (record.header.descriptor.id != 3 or record.header.descriptor.version not in (0, 1)
                            or record.data_length < 8 or not record.data):
                        self.result["invalid_events"] += 1
                        self.failure.set()
                        return
                    pid, tid = struct.unpack("<II", ctypes.string_at(record.data, 8))
                    if pid in self.pids:
                        self.tids[pid].add(tid)
                    else:
                        # 不保存其他进程的 PID、线程 ID 或事件内容。
                        self.result["foreign_events"] += 1
                        self.failure.set()
            except Exception as exc:
                self.result["callback_errors"].append(type(exc).__name__)
                self.failure.set()

        self.callback = on_event

    def start(self, control_guid: etw.GUID):
        self.result["start_status"] = self.advapi.StartTraceW(
            ctypes.byref(self.trace), self.name, ctypes.byref(self.props))
        if self.result["start_status"] != 0:
            raise OSError("无法启动批量探针的独立 ETW 会话。")
        self.started = True
        self.sink({"event": "session_started", "session": self.name})
        self.logfile = etw.TraceLogfile()
        self.logfile.logger_name = self.name
        self.logfile.mode = 0x10000000 | 0x100
        self.logfile.callback = ctypes.cast(self.callback, ctypes.c_void_p)
        self.consumer = etw.U64(self.advapi.OpenTraceW(ctypes.byref(self.logfile)))
        if self.consumer.value == 0xFFFFFFFFFFFFFFFF:
            raise OSError(f"OpenTraceW 失败：{ctypes.get_last_error()}")

        def consume():
            self.trace_status.append(self.advapi.ProcessTrace(ctypes.byref(self.consumer), 1, None, None))

        self.consumer_thread = threading.Thread(target=consume, name=self.name, daemon=True)
        self.consumer_thread.start()
        self.result["control_enable_status"] = etw._enable_pid(
            self.advapi, self.trace, control_guid, os.getpid(), 0)
        kernel_guid = etw.GUID.from_uuid(etw.KERNEL_PROCESS)
        self.result.update(etw._enable_payload(self.advapi, self.trace, kernel_guid, sorted(self.pids)))
        if (self.result["control_enable_status"] != 0 or self.result.get("kernel_enable_status") != 0
                or self.result.get("aggregate_cleanup_status") != 0
                or self.result.get("filter_cleanup_status") != [0, 0]):
            raise OSError("无法安全启用或清理批量线程事件过滤器。")

    def stop(self):
        if self.started:
            self.result["stop_status"] = self.advapi.ControlTraceW(
                self.trace, self.name, ctypes.byref(self.props), 1)
        if self.consumer_thread is not None:
            self.consumer_thread.join(timeout=5)
            if self.consumer_thread.is_alive() and self.consumer is not None:
                self.advapi.CloseTrace(self.consumer)
                self.consumer_thread.join(timeout=2)
            self.result["consumer_finished"] = not self.consumer_thread.is_alive()
            self.result["process_trace_status"] = self.trace_status
            self.result["consumer_events_lost"] = self.logfile.events_lost
        if self.consumer is not None and self.consumer.value != 0xFFFFFFFFFFFFFFFF:
            self.result["close_status"] = self.advapi.CloseTrace(self.consumer)
        self.result["events_lost"] = self.props.events_lost
        self.result["realtime_buffers_lost"] = self.props.realtime_lost
        self.result["thread_ids"] = {str(pid): sorted(tids) for pid, tids in self.tids.items()}


def run_probe(sink=None) -> dict:
    """仅使用两个自建会话和16个固定无害进程，运行前要求管理员令牌。"""
    if os.name != "nt":
        raise OSError("批量线程探针只支持 Windows。")
    shell = ctypes.WinDLL("shell32")
    shell.IsUserAnAdmin.restype = ctypes.c_int
    if not shell.IsUserAnAdmin():
        return {"passed": False, "error": "当前令牌未提升；不启动批量探针。"}
    if sink is None:
        sink = lambda _event: None
    resources = job._resource_gate()
    slots = select_mapping(*read_windows_topology())["workers"]
    advapi, _ = etw._configure_api()
    control_id = uuid.uuid4()
    control_guid = etw.GUID.from_uuid(control_id)
    registration = etw.U64()
    failure = threading.Event()
    jobs = []
    sessions = []
    workers = []
    registered = False
    result = {"passed": False, "scope": "16个受控无害进程；不代表候选隔离通过。",
              "resource_precheck": resources}
    try:
        result["register_status"] = advapi.EventRegister(ctypes.byref(control_guid), None, None,
                                                         ctypes.byref(registration))
        if result["register_status"] != 0:
            raise OSError("无法注册本进程的无害阳性对照事件。")
        registered = True
        for slot in slots:
            if job._available_memory() < 16 * 1024**3:
                raise OSError("可用内存低于16 GiB，停止启动探针。")
            started = time.monotonic()
            probe_job = job._ProbeJob(slot["logical_processor"])
            jobs.append(probe_job)
            process = probe_job.start_thread_probe_suspended(hold_ms=2000)
            workers.append({"process": process, "slot": slot, "started": started})
        pids = [item["process"].pid for item in workers]
        for group in _partitions(pids):
            session = _FilteredSession(advapi, group, control_id, failure, sink)
            sessions.append(session)
            session.start(control_guid)
        descriptor = etw.EventDescriptor()
        descriptor.id, descriptor.level = 77, 4
        result["control_write_status"] = advapi.EventWrite(registration, ctypes.byref(descriptor), 0, None)
        if result["control_write_status"] != 0:
            raise OSError("无法写入无害阳性对照事件。")
        ready_deadline = time.monotonic() + 3
        while any(session.result["control_events"] == 0 for session in sessions):
            if failure.is_set() or time.monotonic() >= ready_deadline:
                raise OSError("批量会话阳性对照未通过。")
            time.sleep(0.02)
        for item, probe_job in zip(workers, jobs):
            if failure.is_set() or time.monotonic() - item["started"] >= job.TIME_LIMIT_SECONDS:
                raise OSError("线程事件异常或探针已超过时限。")
            probe_job.resume(item["process"])
        while any(item["process"].poll() is None for item in workers):
            if failure.is_set():
                raise OSError("线程事件过滤出现异常，立即终止探针。")
            if any(time.monotonic() - item["started"] >= job.TIME_LIMIT_SECONDS
                   and item["process"].poll() is None for item in workers):
                raise OSError("线程探针超过作业时限。")
            time.sleep(0.01)
        for item in workers:
            process = item["process"]
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode != 0 or len(stdout) > job.STDOUT_LIMIT or len(stderr) > job.STDERR_LIMIT:
                raise OSError("线程探针退出失败或输出超限。")
            worker = json.loads(stdout)
            if worker.get("pid") != process.pid:
                raise OSError("线程探针进程身份不一致。")
            if worker["finished_monotonic"] - item["started"] > job.TIME_LIMIT_SECONDS:
                raise OSError("线程探针在作业时限后结束。")
            item["worker"] = worker
        event_deadline = time.monotonic() + 3
        while time.monotonic() < event_deadline and not failure.is_set():
            if all(item["worker"]["ordinary_tid"] in session.tids[item["process"].pid]
                   and item["worker"]["hidden_tid"] in session.tids[item["process"].pid]
                   for session in sessions for item in workers if item["process"].pid in session.pids):
                break
            time.sleep(0.02)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
    finally:
        cleanup_errors = []
        for item, probe_job in zip(workers, jobs):
            try:
                process = item["process"]
                if process.poll() is None:
                    probe_job.terminate()
                if not process.stdout.closed or not process.stderr.closed:
                    process.communicate(timeout=5)
            except Exception as exc:
                cleanup_errors.append(f"worker: {type(exc).__name__}: {exc}")
                try:
                    process.kill()
                    process.communicate(timeout=5)
                except Exception as fallback:
                    cleanup_errors.append(f"worker fallback: {type(fallback).__name__}: {fallback}")
        for session in sessions:
            try:
                session.stop()
            except Exception as exc:
                cleanup_errors.append(f"session {session.name}: {type(exc).__name__}: {exc}")
        if registered:
            try:
                result["unregister_status"] = advapi.EventUnregister(registration)
            except Exception as exc:
                cleanup_errors.append(f"unregister: {type(exc).__name__}: {exc}")
        try:
            query = subprocess.run(["logman", "query", "-ets"], env=etw._probe_environment(),
                                   capture_output=True, check=False, timeout=5)
            result["session_enumeration_status"] = query.returncode
            for session in sessions:
                session.result["session_gone"] = (query.returncode == 0
                                                  and session.name.lower().encode() not in query.stdout.lower())
        except Exception as exc:
            cleanup_errors.append(f"session enumeration: {type(exc).__name__}: {exc}")
        result["sessions"] = [session.result for session in sessions]
        result["workers"] = []
        for item, probe_job in zip(workers, jobs):
            try:
                wait_until = time.monotonic() + 3
                usage = probe_job.accounting()
                while usage["active_processes"] and time.monotonic() < wait_until:
                    time.sleep(0.02)
                    usage = probe_job.accounting()
                result["workers"].append({"pid": item["process"].pid, "slot": item["slot"]["slot"],
                                          "logical_processor": item["slot"]["logical_processor"],
                                          "worker": item.get("worker"), **usage})
            except Exception as exc:
                cleanup_errors.append(f"job accounting: {type(exc).__name__}: {exc}")
        for probe_job in jobs:
            try:
                probe_job.close()
            except Exception as exc:
                cleanup_errors.append(f"job close: {type(exc).__name__}: {exc}")
        result["cleanup_errors"] = cleanup_errors

    complete = (len(sessions) == 2 and len(workers) == 16 and all("worker" in item for item in workers))
    if complete:
        overlap = max(item["worker"]["started_monotonic"] for item in workers) < min(
            item["worker"]["finished_monotonic"] for item in workers)
        threads_seen = all(item["worker"]["ordinary_tid"] in session.tids[item["process"].pid]
                           and item["worker"]["hidden_tid"] in session.tids[item["process"].pid]
                           for session in sessions for item in workers if item["process"].pid in session.pids)
        session_clean = all(session.result.get("start_status") == 0
                            and session.result.get("control_enable_status") == 0
                            and session.result.get("kernel_enable_status") == 0
                            and session.result.get("create_filter_status") == [0, 0]
                            and session.result.get("aggregate_status") == 0
                            and session.result.get("aggregate_cleanup_status") == 0
                            and session.result.get("filter_cleanup_status") == [0, 0]
                            and session.result.get("control_events", 0) >= 1
                            and session.result.get("stop_status") == 0
                            and session.result.get("close_status") == 0
                            and session.result.get("consumer_finished") is True
                            and session.result.get("process_trace_status") == [0]
                            and session.result.get("session_gone") is True
                            and session.result.get("events_lost") == 0
                            and session.result.get("realtime_buffers_lost") == 0
                            and session.result.get("consumer_events_lost") == 0
                            and session.result.get("foreign_events") == 0
                            and session.result.get("invalid_events") == 0
                            and not session.result.get("callback_errors") for session in sessions)
        result.update({"simultaneous_16": overlap, "all_expected_threads_seen": threads_seen})
        workers_valid = (len(result["workers"]) == 16 and all(
            item["active_processes"] == 0 and item["worker"]["affinity"] == 1 << item["logical_processor"]
            and item["worker"]["priority"] == 0x20 for item in result["workers"]))
        result["passed"] = (not result.get("error") and overlap and threads_seen and session_clean
                            and not result["cleanup_errors"] and workers_valid
                            and result.get("control_write_status") == 0
                            and result.get("unregister_status") == 0
                            and result.get("session_enumeration_status") == 0)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="只验证16个自建线程探针，不执行候选。")
    parser.add_argument("--record", required=True, help="outputs 中新建 p0_task3_etw_batch_*.jsonl")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_etw_batch_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名须为 p0_task3_etw_batch_*.jsonl，且不能包含路径。")
    path = ROOT / "outputs" / options.record
    with path.open("x", encoding="utf-8", newline="\n") as record:
        def save(event):
            record.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            record.flush()
        sources = [Path(__file__), ROOT / "scripts" / "p0_etw_pid_probe.py", ROOT / "scripts" / "p0_job_probe.py",
                   ROOT / "scripts" / "p0_thread_probe.py", ROOT / "scripts" / "p0_cpu_topology.py"]
        save({"event": "sources", "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                               for path in sources}})
        try:
            result = run_probe(save)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
