"""只执行本项目无害探针，核验 Windows 作业对象；不是候选隔离执行器。"""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

if __package__:
    from .p0_cpu_topology import read_windows_topology, select_mapping
else:
    from p0_cpu_topology import read_windows_topology, select_mapping


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "p0_job_probe_worker.py"
THREAD_WORKER = ROOT / "scripts" / "p0_thread_probe.py"
MEMORY_LIMIT = 512 * 1024 * 1024
STDOUT_LIMIT = 16 * 1024
STDERR_LIMIT = 64 * 1024
TIME_LIMIT_SECONDS = 15


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [("user", ctypes.c_int64), ("kernel", ctypes.c_int64),
                ("period_user", ctypes.c_int64), ("period_kernel", ctypes.c_int64),
                ("faults", wintypes.DWORD), ("total_processes", wintypes.DWORD),
                ("active_processes", wintypes.DWORD), ("terminated_processes", wintypes.DWORD)]


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                ("total_physical", ctypes.c_uint64), ("available_physical", ctypes.c_uint64),
                ("total_pagefile", ctypes.c_uint64), ("available_pagefile", ctypes.c_uint64),
                ("total_virtual", ctypes.c_uint64), ("available_virtual", ctypes.c_uint64),
                ("available_extended_virtual", ctypes.c_uint64)]


class FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    def value(self) -> int:
        return (self.high << 32) | self.low


def _available_memory() -> int:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return status.available_physical


def _cpu_sample(seconds: float = 0.5) -> float:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemTimes.argtypes = [ctypes.POINTER(FileTime), ctypes.POINTER(FileTime), ctypes.POINTER(FileTime)]
    kernel.GetSystemTimes.restype = wintypes.BOOL

    def read() -> tuple[int, int, int]:
        idle, kernel_time, user = FileTime(), FileTime(), FileTime()
        if not kernel.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel_time), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        return idle.value(), kernel_time.value(), user.value()

    before = read()
    time.sleep(seconds)
    after = read()
    total = (after[1] - before[1]) + (after[2] - before[2])
    idle = after[0] - before[0]
    if total <= 0 or not 0 <= idle <= total:
        raise OSError("无法可靠计算系统 CPU 占用。")
    return 100 * (total - idle) / total


def _resource_gate() -> dict:
    if _available_memory() < 16 * 1024**3:
        raise OSError("可用内存低于 16 GiB，暂停新探针。")
    cpu = [_cpu_sample(), _cpu_sample()]
    memory = _available_memory()
    if memory < 16 * 1024**3 or all(value > 85 for value in cpu):
        raise OSError("资源检查不满足 P0 条件，暂停新探针。")
    return {"available_memory_bytes": memory, "cpu_percent_samples": cpu}


def _apis():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("作业对象探针只支持 64 位 Windows。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return kernel, ntdll


class _ProbeJob:
    def __init__(self, logical_processor: int):
        self.kernel, self.ntdll = _apis()
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        # 暂只探测活动进程、亲和性和提交量；工作集上限仍未通过，不允许运行候选。
        limits.basic.flags = 0x0008 | 0x0010 | 0x0100 | 0x0200 | 0x2000
        limits.basic.active_limit = 1
        limits.basic.affinity = 1 << logical_processor
        limits.process_memory = limits.job_memory = MEMORY_LIMIT
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def _start_owned_worker(self, mode: str, suspended: bool, hold_ms: int = 0):
        if mode not in {"identity", "child", "memory", "mapping", "timeout", "stdout", "stderr", "thread_probe"}:
            raise ValueError("只允许运行项目自带的无害探针。")
        executable = THREAD_WORKER if mode == "thread_probe" else WORKER
        if hold_ms not in (0, 2000) or (mode != "thread_probe" and hold_ms):
            raise ValueError("无效的无害探针等待时间。")
        arguments = (["--hold-ms", str(hold_ms)] if mode == "thread_probe" else [mode])
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        environment = {"SystemRoot": system_root, "WINDIR": system_root,
                       "PATH": os.path.join(system_root, "System32")}
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(executable), *arguments], cwd=ROOT, env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS,
        )
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not suspended:
                self.resume(process)
            return process
        except BaseException:
            process.kill()
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()
            raise

    def start_worker(self, mode: str):
        if mode == "thread_probe":
            raise ValueError("线程探针只能通过挂起入口启动。")
        return self._start_owned_worker(mode, False)

    def start_thread_probe_suspended(self, hold_ms: int = 0):
        return self._start_owned_worker("thread_probe", True, hold_ms)

    def resume(self, process):
        status = self.ntdll.NtResumeProcess(int(process._handle))
        if status != 0:
            raise OSError(f"NtResumeProcess 失败：0x{status & 0xffffffff:08x}")

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def accounting(self) -> dict:
        accounting = Accounting()
        limits = ExtendedLimits()
        for kind, value in ((1, accounting), (9, limits)):
            if not self.kernel.QueryInformationJobObject(self.handle, kind, ctypes.byref(value),
                                                        ctypes.sizeof(value), None):
                raise ctypes.WinError(ctypes.get_last_error())
        return {"cpu_seconds": (accounting.user + accounting.kernel) / 10_000_000,
                "total_processes": accounting.total_processes,
                "active_processes": accounting.active_processes,
                "peak_process_commit_bytes": limits.peak_process_memory,
                "peak_job_commit_bytes": limits.peak_job_memory}

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class _BoundedReader:
    def __init__(self, stream, limit: int):
        self.stream, self.limit = stream, limit
        self.data = bytearray()
        self.observed = 0
        self.exceeded = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self):
        try:
            while True:
                chunk = os.read(self.stream.fileno(), 4096)
                if not chunk:
                    break
                self.observed += len(chunk)
                self.data.extend(chunk[:max(0, self.limit - len(self.data))])
                if self.observed > self.limit:
                    self.exceeded.set()
                    break
        except OSError as exc:
            self.error = str(exc)


def run_worker(mode: str, slot: dict) -> dict:
    """监督固定无害探针；此函数没有外部程序或命令参数。"""
    if _available_memory() < 16 * 1024**3:
        raise OSError("可用内存低于 16 GiB，暂停新探针。")
    started = time.monotonic()
    job = _ProbeJob(slot["logical_processor"])
    process = None
    try:
        process = job.start_worker(mode)
        resumed = time.monotonic()
        readers = [_BoundedReader(process.stdout, STDOUT_LIMIT), _BoundedReader(process.stderr, STDERR_LIMIT)]
        for reader in readers:
            reader.thread.start()
        reason = "exited"
        while process.poll() is None:
            if readers[0].exceeded.is_set() or readers[1].exceeded.is_set():
                reason = "stdout_limit" if readers[0].exceeded.is_set() else "stderr_limit"
                job.terminate()
                break
            if time.monotonic() - started >= TIME_LIMIT_SECONDS:
                reason = "timeout"
                job.terminate()
                break
            time.sleep(0.01)
        process.wait(timeout=5)
        for reader in readers:
            reader.thread.join(timeout=3)
        if any(reader.thread.is_alive() or reader.error for reader in readers):
            raise OSError("探针输出读取器未结束或读取失败。")
        finished = time.monotonic()
        if reason == "exited" and readers[0].exceeded.is_set():
            reason = "stdout_limit"
        if reason == "exited" and readers[1].exceeded.is_set():
            reason = "stderr_limit"
        if reason == "exited" and finished - started > TIME_LIMIT_SECONDS:
            reason = "timeout"
        end_wait = time.monotonic() + 3
        usage = job.accounting()
        while usage["active_processes"] and time.monotonic() < end_wait:
            time.sleep(0.02)
            usage = job.accounting()
        worker = None
        if reason == "exited" and readers[0].data:
            worker = json.loads(readers[0].data)
        return {"mode": mode, "slot": slot["slot"], "logical_processor": slot["logical_processor"],
                "pid": process.pid, "exit_code": process.returncode, "reason": reason,
                "elapsed_seconds": finished - started, "resumed_monotonic": resumed,
                "finished_monotonic": finished, "stdout_bytes_observed": readers[0].observed,
                "stderr_bytes_observed": readers[1].observed, "worker": worker, **usage}
    finally:
        if process is not None and process.poll() is None:
            job.terminate()
            process.wait(timeout=5)
        if process is not None:
            process.stdout.close()
            process.stderr.close()
        job.close()


def _valid(result: dict) -> bool:
    if result["active_processes"] != 0:
        return False
    mode, worker = result["mode"], result["worker"]
    if mode != "timeout" and result.get("elapsed_seconds", float("inf")) > TIME_LIMIT_SECONDS:
        return False
    if mode in {"identity", "child", "memory"} and type(worker) is not dict:
        return False
    if mode == "identity":
        return (result["reason"] == "exited" and result["exit_code"] == 0
                and worker["pid"] == result["pid"]
                and worker["affinity"] == 1 << result["logical_processor"]
                and worker["priority"] == 0x20
                and worker["working_set_bytes"] <= MEMORY_LIMIT)
    if mode == "child":
        return (result["reason"] == "exited" and result["exit_code"] == 0
                and worker.get("blocked") is True and worker.get("winerror") == 1816)
    if mode == "memory":
        return (result["reason"] == "exited" and result["exit_code"] == 0
                and worker.get("blocked") is True and worker["working_set_bytes"] <= MEMORY_LIMIT
                and worker["private_commit_bytes"] <= MEMORY_LIMIT
                and result["peak_job_commit_bytes"] <= MEMORY_LIMIT)
    if mode == "timeout":
        return result["reason"] == "timeout" and result["exit_code"] != 0
    return (result["reason"] == f"{mode}_limit" and result["exit_code"] != 0
            and result[f"{mode}_bytes_observed"] > (STDOUT_LIMIT if mode == "stdout" else STDERR_LIMIT))


def run_case(case: str) -> dict:
    """只核验作业资源限制；不验证 AppContainer、网络或线程。"""
    resources = _resource_gate()
    slots = select_mapping(*read_windows_topology())["workers"]
    if case == "parallel":
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(lambda slot: run_worker("identity", slot), slots))
        valid_workers = all(_valid(item) for item in results)
        overlap = valid_workers and max(item["worker"]["started_monotonic"] for item in results) < min(
            item["worker"]["finished_monotonic"] for item in results)
        passed = overlap and len({item["logical_processor"] for item in results}) == 16
    elif case == "basic":
        results = [run_worker(mode, slots[0]) for mode in ("identity", "child", "memory", "stdout", "stderr")]
        overlap, passed = None, True
    elif case == "timeout":
        results = [run_worker("timeout", slots[0])]
        overlap, passed = None, True
    else:
        raise ValueError("未知的探针组。")
    passed = passed and all(_valid(item) for item in results)
    return {"case": case, "passed": passed, "simultaneous_16": overlap, "resource_precheck": resources,
            "scope": "仅可信无害探针；未核验工作集上限、网络、数据或线程隔离，禁止执行候选。",
            "results": results}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="核验 Windows 作业资源限制，不执行候选。")
    parser.add_argument("--case", required=True, choices=("basic", "parallel", "timeout"))
    options = parser.parse_args()
    try:
        result = run_case(options.case)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        result = {"case": options.case, "passed": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
