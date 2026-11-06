"""任务3专用的无害作业探针；不加载或执行候选程序。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
import time


class MemoryCounters(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("page_faults", wintypes.DWORD),
                ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t),
                ("peak_paged_pool", ctypes.c_size_t), ("paged_pool", ctypes.c_size_t),
                ("peak_nonpaged_pool", ctypes.c_size_t), ("nonpaged_pool", ctypes.c_size_t),
                ("pagefile", ctypes.c_size_t), ("peak_pagefile", ctypes.c_size_t),
                ("private_usage", ctypes.c_size_t)]


def _process_info() -> dict:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]
    kernel.GetPriorityClass.restype = wintypes.DWORD
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.GetCurrentProcess()
    mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    counters = MemoryCounters()
    counters.size = ctypes.sizeof(counters)
    if (not kernel.GetProcessAffinityMask(handle, ctypes.byref(mask), ctypes.byref(system_mask))
            or not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.size)):
        raise OSError(f"读取探针进程信息失败：{ctypes.get_last_error()}")
    return {"pid": os.getpid(), "affinity": mask.value, "priority": kernel.GetPriorityClass(handle),
            "working_set_bytes": counters.working_set, "peak_working_set_bytes": counters.peak_working_set,
            "private_commit_bytes": counters.private_usage}


def main() -> int:
    if os.name != "nt" or len(sys.argv) != 2:
        raise RuntimeError("仅允许由 Windows 作业探针传入一种已定义模式。")
    mode = sys.argv[1]
    if mode == "identity":
        result = _process_info()
        result["started_monotonic"] = time.monotonic()
        time.sleep(2)
        result["finished_monotonic"] = time.monotonic()
        print(json.dumps(result), flush=True)
    elif mode == "child":
        try:
            child = subprocess.run([sys.executable, "-I", "-B", "-c", "pass"], timeout=5, check=False)
            result = {"blocked": False, "child_exit": child.returncode}
        except OSError as exc:
            result = {"blocked": True, "winerror": getattr(exc, "winerror", None)}
        print(json.dumps(result), flush=True)
    elif mode == "memory":
        try:
            allocation = bytearray(600 * 1024 * 1024)
        except MemoryError:
            result = {"blocked": True, **_process_info()}
        else:
            result = {"blocked": False, "allocation_bytes": len(allocation), **_process_info()}
        print(json.dumps(result), flush=True)
    elif mode == "mapping":
        path = Path(sys.executable).parent / "python313.dll"
        views, checksum = [], 0
        before = _process_info()
        with path.open("rb") as source:
            for _ in range(20):
                view = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
                views.append(view)
                for offset in range(0, len(view), 4096):
                    checksum ^= view[offset]
            after = _process_info()
            result = {"file_bytes": path.stat().st_size, "views": len(views), "checksum": checksum,
                      "before": before, "after": after}
            print(json.dumps(result), flush=True)
        for view in views:
            view.close()
    elif mode == "timeout":
        time.sleep(30)
    elif mode == "working_set":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                                       ctypes.POINTER(ctypes.c_size_t),
                                                       ctypes.POINTER(wintypes.DWORD)]
        kernel.GetProcessWorkingSetSizeEx.restype = wintypes.BOOL
        kernel.SetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.c_size_t,
                                                       ctypes.c_size_t, wintypes.DWORD]
        kernel.SetProcessWorkingSetSizeEx.restype = wintypes.BOOL
        handle = kernel.GetCurrentProcess()
        minimum, maximum, before, after = (ctypes.c_size_t(), ctypes.c_size_t(),
                                            wintypes.DWORD(), wintypes.DWORD())
        if not kernel.GetProcessWorkingSetSizeEx(handle, ctypes.byref(minimum), ctypes.byref(maximum),
                                                 ctypes.byref(before)):
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.set_last_error(0)
        changed = kernel.SetProcessWorkingSetSizeEx(handle, minimum.value, maximum.value, 0x8)
        error = 0 if changed else ctypes.get_last_error()
        if not kernel.GetProcessWorkingSetSizeEx(handle, ctypes.byref(minimum), ctypes.byref(maximum),
                                                 ctypes.byref(after)):
            raise ctypes.WinError(ctypes.get_last_error())
        print(json.dumps({"before_flags": before.value, "disable_success": bool(changed),
                          "disable_error": error, "after_flags": after.value,
                          "maximum_bytes": maximum.value}), flush=True)
    elif mode in ("stdout", "stderr"):
        stream = sys.stdout.buffer if mode == "stdout" else sys.stderr.buffer
        limit = 16 * 1024 if mode == "stdout" else 64 * 1024
        stream.write(b"x" * (limit + 1))
        stream.flush()
        time.sleep(10)
    else:
        raise ValueError("未知的受控探针模式。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
