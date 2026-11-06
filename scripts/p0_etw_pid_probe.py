"""核验 PID 过滤能否覆盖目标进程的普通与隐藏线程；不构建或执行候选。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
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


ROOT = Path(__file__).resolve().parents[1]
KERNEL_PROCESS = uuid.UUID("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716")
U32 = ctypes.c_uint32
U64 = ctypes.c_uint64


class GUID(ctypes.Structure):
    _fields_ = [("data", ctypes.c_byte * 16)]

    @classmethod
    def from_uuid(cls, value: uuid.UUID):
        return cls.from_buffer_copy(value.bytes_le)


class Wnode(ctypes.Structure):
    _fields_ = [("size", U32), ("provider", U32), ("historical", U64),
                ("timestamp", ctypes.c_int64), ("guid", GUID), ("client", U32), ("flags", U32)]


class TraceProperties(ctypes.Structure):
    _fields_ = [("wnode", Wnode), ("buffer_size", U32), ("min_buffers", U32),
                ("max_buffers", U32), ("max_file_size", U32), ("mode", U32),
                ("flush_timer", U32), ("enable_flags", U32), ("age_limit", U32),
                ("buffers", U32), ("free_buffers", U32), ("events_lost", U32),
                ("buffers_written", U32), ("log_buffers_lost", U32), ("realtime_lost", U32),
                ("logger_thread", wintypes.HANDLE), ("file_offset", U32), ("name_offset", U32)]


class SessionBuffer(ctypes.Structure):
    _fields_ = [("properties", TraceProperties), ("name", ctypes.c_wchar * 128)]


class EventDescriptor(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint16), ("version", ctypes.c_uint8),
                ("channel", ctypes.c_uint8), ("level", ctypes.c_uint8),
                ("opcode", ctypes.c_uint8), ("task", ctypes.c_uint16), ("keyword", U64)]


class EventHeader(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint16), ("header_type", ctypes.c_uint16),
                ("flags", ctypes.c_uint16), ("property", ctypes.c_uint16),
                ("thread_id", U32), ("process_id", U32), ("timestamp", ctypes.c_int64),
                ("provider", GUID), ("descriptor", EventDescriptor), ("processor_time", U64),
                ("activity", GUID)]


class EventRecord(ctypes.Structure):
    _fields_ = [("header", EventHeader), ("buffer_context", U32),
                ("extended_count", ctypes.c_uint16), ("data_length", ctypes.c_uint16),
                ("extended", ctypes.c_void_p), ("data", ctypes.c_void_p), ("context", ctypes.c_void_p)]


EventCallback = ctypes.WINFUNCTYPE(None, ctypes.POINTER(EventRecord)) if os.name == "nt" else None


class TraceLogfile(ctypes.Structure):
    # 前两段只占位；本探针不访问旧式 EVENT_TRACE 与 TRACE_LOGFILE_HEADER。
    _fields_ = [("file_name", ctypes.c_wchar_p), ("logger_name", ctypes.c_wchar_p),
                ("current_time", ctypes.c_int64), ("buffers_read", U32), ("mode", U32),
                ("current_event", ctypes.c_byte * 88), ("logfile_header", ctypes.c_byte * 280),
                ("buffer_callback", ctypes.c_void_p), ("buffer_size", U32), ("filled", U32),
                ("events_lost", U32), ("callback", ctypes.c_void_p), ("is_kernel", U32),
                ("context", ctypes.c_void_p)]


class FilterDescriptor(ctypes.Structure):
    _fields_ = [("ptr", U64), ("size", U32), ("type", U32)]


class EnableParameters(ctypes.Structure):
    _fields_ = [("version", U32), ("property", U32), ("flags", U32), ("source", GUID),
                ("filters", ctypes.POINTER(FilterDescriptor)), ("filter_count", U32)]


class PayloadPredicate(ctypes.Structure):
    _fields_ = [("name", ctypes.c_wchar_p), ("operator", ctypes.c_uint16),
                ("value", ctypes.c_wchar_p)]


class EventIdFilter(ctypes.Structure):
    _fields_ = [("include", ctypes.c_uint8), ("reserved", ctypes.c_uint8),
                ("count", ctypes.c_uint16), ("ids", ctypes.c_uint16 * 1)]


def _configure_api():
    expected = {TraceProperties: 120, TraceLogfile: 448, EventHeader: 80,
                EventRecord: 112, EnableParameters: 48}
    if os.name != "nt" or any(ctypes.sizeof(item) != size for item, size in expected.items()):
        raise RuntimeError("ETW 探针仅支持核验过结构布局的 64 位 Windows。")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.StartTraceW.argtypes = [ctypes.POINTER(U64), ctypes.c_wchar_p, ctypes.POINTER(TraceProperties)]
    advapi.StartTraceW.restype = U32
    advapi.ControlTraceW.argtypes = [U64, ctypes.c_wchar_p, ctypes.POINTER(TraceProperties), U32]
    advapi.ControlTraceW.restype = U32
    advapi.OpenTraceW.argtypes = [ctypes.POINTER(TraceLogfile)]
    advapi.OpenTraceW.restype = U64
    advapi.ProcessTrace.argtypes = [ctypes.POINTER(U64), U32, ctypes.c_void_p, ctypes.c_void_p]
    advapi.ProcessTrace.restype = U32
    advapi.CloseTrace.argtypes = [U64]
    advapi.CloseTrace.restype = U32
    advapi.EnableTraceEx2.argtypes = [U64, ctypes.POINTER(GUID), U32, ctypes.c_uint8,
                                      U64, U64, U32, ctypes.POINTER(EnableParameters)]
    advapi.EnableTraceEx2.restype = U32
    advapi.EventRegister.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.POINTER(U64)]
    advapi.EventRegister.restype = U32
    advapi.EventWrite.argtypes = [U64, ctypes.POINTER(EventDescriptor), U32, ctypes.c_void_p]
    advapi.EventWrite.restype = U32
    advapi.EventUnregister.argtypes = [U64]
    advapi.EventUnregister.restype = U32
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return advapi, ntdll


def _enable_pid(advapi, trace: U64, provider: GUID, pid: int, keyword: int) -> int:
    pids = (U32 * 1)(pid)
    descriptor = FilterDescriptor(ctypes.addressof(pids), ctypes.sizeof(pids), 0x80000004)
    parameters = EnableParameters()
    parameters.version = 2
    parameters.filters = ctypes.pointer(descriptor)
    parameters.filter_count = 1
    return advapi.EnableTraceEx2(trace, ctypes.byref(provider), 1, 4, keyword, 0, 5000,
                                 ctypes.byref(parameters))


def _payload_predicates(pids: list[int]) -> ctypes.Array:
    if (type(pids) is not list or not 1 <= len(pids) <= 8
            or any(type(pid) is not int or not 0 < pid <= 0xFFFFFFFF for pid in pids)
            or len(set(pids)) != len(pids)):
        raise ValueError("每个会话须提供1至8个互异、有效的目标 PID。")
    return (PayloadPredicate * len(pids))(*(PayloadPredicate("ProcessID", 0, str(pid)) for pid in pids))


def _enable_payload(advapi, trace: U64, provider: GUID, pids: list[int]) -> dict:
    """以最多8个事件负载 ProcessID 和事件 ID 过滤内核线程创建事件。"""
    predicates = _payload_predicates(pids)
    tdh = ctypes.WinDLL("tdh", use_last_error=True)
    tdh.TdhCreatePayloadFilter.argtypes = [ctypes.POINTER(GUID), ctypes.POINTER(EventDescriptor),
                                           ctypes.c_uint8, U32, ctypes.POINTER(PayloadPredicate),
                                           ctypes.POINTER(ctypes.c_void_p)]
    tdh.TdhCreatePayloadFilter.restype = U32
    tdh.TdhAggregatePayloadFilters.argtypes = [U32, ctypes.POINTER(ctypes.c_void_p),
                                               ctypes.c_void_p, ctypes.POINTER(FilterDescriptor)]
    tdh.TdhAggregatePayloadFilters.restype = U32
    tdh.TdhCleanupPayloadEventFilterDescriptor.argtypes = [ctypes.POINTER(FilterDescriptor)]
    tdh.TdhCleanupPayloadEventFilterDescriptor.restype = U32
    tdh.TdhDeletePayloadFilter.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    tdh.TdhDeletePayloadFilter.restype = U32
    filters = (ctypes.c_void_p * 2)()
    aggregate = FilterDescriptor()
    statuses = {"create_filter_status": []}
    try:
        for version in (0, 1):
            event = EventDescriptor(3, version, 16, 4, 1, 3, 0x8000000000000020)
            destination = ctypes.cast(ctypes.byref(filters, version * ctypes.sizeof(ctypes.c_void_p)),
                                      ctypes.POINTER(ctypes.c_void_p))
            status = tdh.TdhCreatePayloadFilter(ctypes.byref(provider), ctypes.byref(event), 1, len(pids),
                                                 predicates, destination)
            statuses["create_filter_status"].append(status)
            if status != 0:
                return statuses
        statuses["aggregate_status"] = tdh.TdhAggregatePayloadFilters(2, filters, None,
                                                                     ctypes.byref(aggregate))
        if statuses["aggregate_status"] != 0:
            return statuses
        event_ids = EventIdFilter(1, 0, 1, (ctypes.c_uint16 * 1)(3))
        descriptors = (FilterDescriptor * 2)(
            aggregate, FilterDescriptor(ctypes.addressof(event_ids), ctypes.sizeof(event_ids), 0x80000200)
        )
        parameters = EnableParameters()
        parameters.version = 2
        parameters.filters = descriptors
        parameters.filter_count = 2
        statuses["kernel_enable_status"] = advapi.EnableTraceEx2(
            trace, ctypes.byref(provider), 1, 4, 0x20, 0, 5000, ctypes.byref(parameters)
        )
        return statuses
    finally:
        if aggregate.ptr:
            statuses["aggregate_cleanup_status"] = tdh.TdhCleanupPayloadEventFilterDescriptor(
                ctypes.byref(aggregate))
        statuses["filter_cleanup_status"] = [
            tdh.TdhDeletePayloadFilter(ctypes.cast(
                ctypes.byref(filters, index * ctypes.sizeof(ctypes.c_void_p)), ctypes.POINTER(ctypes.c_void_p)))
            for index in range(2) if filters[index]
        ]


def _probe_passed(result: dict, own_tids: set[int], callback_errors: list) -> bool:
    zero_statuses = ("register_status", "start_status", "control_enable_status", "control_write_status",
                     "kernel_enable_status", "resume_status", "worker_exit", "stop_status", "close_status",
                     "unregister_status", "session_enumeration_status")
    worker = result.get("worker", {})
    if type(worker) is not dict:
        return False
    ordinary, hidden = worker.get("ordinary_tid"), worker.get("hidden_tid")
    payload_clean = (result.get("mode") != "payload" or
                     (result.get("create_filter_status") == [0, 0] and result.get("aggregate_status") == 0
                      and result.get("aggregate_cleanup_status") == 0
                      and result.get("filter_cleanup_status") == [0, 0]))
    return (
        not result.get("error") and all(result.get(name) == 0 for name in zero_statuses)
        and result.get("control_events", 0) >= 1 and worker.get("pid") == result.get("target_pid")
        and type(ordinary) is int and type(hidden) is int and ordinary > 0 and hidden > 0 and ordinary != hidden
        and ordinary in own_tids and hidden in own_tids
        and result.get("foreign_events") == 0 and result.get("invalid_events") == 0
        and result.get("events_lost") == 0 and result.get("realtime_buffers_lost") == 0
        and result.get("consumer_events_lost") == 0 and not callback_errors and payload_clean
        and result.get("consumer_finished") is True and result.get("process_trace_status") == [0]
        and result.get("session_gone") is True
    )


def _probe_environment() -> dict:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return {"SystemRoot": root, "WINDIR": root, "PATH": os.path.join(root, "System32")}


def run_probe(mode: str = "pid", event_sink=None) -> dict:
    """只控制本次唯一命名的会话，不接触已有 ETW 会话。"""
    advapi, ntdll = _configure_api()
    name = "P0Task3-" + uuid.uuid4().hex
    user_uuid = uuid.uuid4()
    user_guid = GUID.from_uuid(user_uuid)
    kernel_guid = GUID.from_uuid(KERNEL_PROCESS)
    session = SessionBuffer()
    props = session.properties
    props.wnode.size = ctypes.sizeof(session)
    props.wnode.client = 1
    props.wnode.flags = 0x00020000
    props.buffer_size, props.min_buffers, props.max_buffers = 64, 2, 4
    props.mode, props.flush_timer = 0x100, 1  # EVENT_TRACE_REAL_TIME_MODE
    props.name_offset = ctypes.sizeof(TraceProperties)
    trace = U64()
    user_registration = U64()
    consumer = None
    consumer_thread = None
    process = None
    started = False
    registered = False
    target_pid = None
    own_tids = set()
    foreign_event = threading.Event()
    counters = {"control_events": 0, "foreign_events": 0, "invalid_events": 0}
    result = {"session": name, "mode": mode, "passed": False}
    callback_errors = []

    @EventCallback
    def on_event(record_ptr):
        try:
            record = record_ptr.contents
            provider = bytes(record.header.provider.data)
            if provider == user_uuid.bytes_le and record.header.descriptor.id == 77:
                counters["control_events"] += 1
            elif provider == KERNEL_PROCESS.bytes_le and record.header.descriptor.id == 3:
                if record.header.descriptor.version not in (0, 1) or record.data_length < 8 or not record.data:
                    counters["invalid_events"] += 1
                    return
                pid, tid = struct.unpack("<II", ctypes.string_at(record.data, 8))
                if pid == target_pid:
                    own_tids.add(tid)
                else:
                    # 不保存其他进程的 PID、线程 ID 或事件内容。
                    counters["foreign_events"] += 1
                    foreign_event.set()
        except Exception as exc:
            callback_errors.append(type(exc).__name__)

    try:
        result["register_status"] = advapi.EventRegister(ctypes.byref(user_guid), None, None,
                                                         ctypes.byref(user_registration))
        if result["register_status"] != 0:
            raise OSError("无法注册本进程的无害阳性对照事件。")
        registered = True
        result["start_status"] = advapi.StartTraceW(ctypes.byref(trace), name, ctypes.byref(props))
        if result["start_status"] != 0:
            raise OSError("无法启动本次独立 ETW 会话。")
        started = True
        print(f"已创建本次 ETW 会话：{name}", file=sys.stderr, flush=True)
        if event_sink is not None:
            event_sink({"event": "session_started", "session": name})
        logfile = TraceLogfile()
        logfile.logger_name = name
        logfile.mode = 0x10000000 | 0x100  # EVENT_RECORD | REAL_TIME
        logfile.callback = ctypes.cast(on_event, ctypes.c_void_p)
        consumer = U64(advapi.OpenTraceW(ctypes.byref(logfile)))
        if consumer.value == 0xFFFFFFFFFFFFFFFF:
            raise OSError(f"OpenTraceW 失败：{ctypes.get_last_error()}")
        trace_status = []

        def consume():
            trace_status.append(advapi.ProcessTrace(ctypes.byref(consumer), 1, None, None))

        consumer_thread = threading.Thread(target=consume, name="p0-etw-probe", daemon=True)
        consumer_thread.start()
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(ROOT / "scripts" / "p0_thread_probe.py")],
            cwd=ROOT, env=_probe_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW,
        )
        target_pid = process.pid
        result["target_pid"] = target_pid
        result["control_enable_status"] = _enable_pid(advapi, trace, user_guid, os.getpid(), 0)
        if result["control_enable_status"] != 0:
            raise OSError("无法按 PID 启用阳性对照事件提供者。")
        event = EventDescriptor()
        event.id, event.level = 77, 4
        result["control_write_status"] = advapi.EventWrite(user_registration, ctypes.byref(event), 0, None)
        if result["control_write_status"] != 0:
            raise OSError("无法写入阳性对照事件。")
        deadline = time.monotonic() + 3
        while counters["control_events"] == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        if counters["control_events"] == 0:
            raise OSError("阳性对照未收到事件，不能判断线程过滤是否有效。")
        if mode == "payload":
            result.update(_enable_payload(advapi, trace, kernel_guid, [target_pid]))
        else:
            result["kernel_enable_status"] = _enable_pid(advapi, trace, kernel_guid, target_pid, 0x20)
        if result.get("kernel_enable_status") != 0:
            raise OSError("无法按 PID 启用内核线程事件提供者。")
        result["resume_status"] = ntdll.NtResumeProcess(int(process._handle))
        if result["resume_status"] != 0:
            raise OSError("无法恢复受控线程探针。")
        deadline = time.monotonic() + 8
        while process.poll() is None:
            if foreign_event.is_set():
                raise OSError("过滤器收到非目标线程事件，立即停止探针。")
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(process.args, 8)
            time.sleep(0.01)
        stdout, stderr = process.communicate(timeout=1)
        result["worker_exit"] = process.returncode
        result["worker_stderr"] = stderr.decode("utf-8", errors="replace")[:1024]
        if process.returncode != 0:
            raise OSError("受控线程探针执行失败。")
        result["worker"] = json.loads(stdout)
        if result["worker"].get("pid") != target_pid:
            raise OSError("受控线程进程身份不一致。")
        # 等待缓冲刷新；发现非目标事件立即终止本次会话。
        if foreign_event.wait(1.2):
            raise OSError("过滤器收到非目标线程事件，立即停止探针。")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        if started:
            result["stop_status"] = advapi.ControlTraceW(trace, name, ctypes.byref(props), 1)
        if consumer_thread is not None:
            consumer_thread.join(timeout=5)
            if consumer_thread.is_alive() and consumer is not None:
                advapi.CloseTrace(consumer)
                consumer_thread.join(timeout=2)
            result["consumer_finished"] = not consumer_thread.is_alive()
            result["process_trace_status"] = trace_status
            result["consumer_events_lost"] = logfile.events_lost
        if consumer is not None and consumer.value != 0xFFFFFFFFFFFFFFFF:
            result["close_status"] = advapi.CloseTrace(consumer)
        if registered:
            result["unregister_status"] = advapi.EventUnregister(user_registration)
        if started:
            query = subprocess.run(["logman", "query", "-ets"], env=_probe_environment(),
                                   capture_output=True, check=False)
            result["session_enumeration_status"] = query.returncode
            result["session_gone"] = query.returncode == 0 and name.lower().encode() not in query.stdout.lower()
        result["events_lost"] = props.events_lost
        result["realtime_buffers_lost"] = props.realtime_lost
        result["callback_errors"] = callback_errors
        result.update(counters)
        result["own_thread_ids"] = sorted(own_tids)

    result["passed"] = _probe_passed(result, own_tids, callback_errors)
    return result


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="只对自建无害进程验证 ETW 过滤与线程事件。")
    parser.add_argument("--mode", choices=("pid", "payload"), default="pid")
    parser.add_argument("--record", help="在 outputs 新建 p0_task3_etw_*.jsonl 记录；不得覆盖")
    options = parser.parse_args()
    if options.record and not re.fullmatch(r"p0_task3_etw_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名须为 p0_task3_etw_*.jsonl，且不能包含路径。")

    def execute(stream=None):
        def save(event):
            if stream is not None:
                stream.write(json.dumps(event, ensure_ascii=True) + "\n")
                stream.flush()
        try:
            result = run_probe(options.mode, save)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
        return result

    if options.record:
        with (ROOT / "outputs" / options.record).open("x", encoding="utf-8", newline="\n") as record:
            result = execute(record)
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
