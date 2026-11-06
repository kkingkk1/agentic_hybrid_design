"""仅供任务3核验：创建一条普通线程和一条隐藏调试事件的无害线程。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import time


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("线程探针只支持 Windows。")
    parser = argparse.ArgumentParser(description="创建普通和隐藏调试事件的无害线程。")
    parser.add_argument("--hold-ms", type=int, choices=(0, 2000), default=0)
    options = parser.parse_args()
    started = time.monotonic()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]
    kernel.GetPriorityClass.restype = wintypes.DWORD
    kernel.GetThreadId.argtypes = [wintypes.HANDLE]
    kernel.GetThreadId.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll.NtCreateThreadEx.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, ctypes.c_void_p, wintypes.HANDLE,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, ctypes.c_size_t, ctypes.c_size_t,
        ctypes.c_size_t, ctypes.c_void_p,
    ]
    ntdll.NtCreateThreadEx.restype = ctypes.c_long
    affinity, system_affinity = ctypes.c_size_t(), ctypes.c_size_t()
    current = kernel.GetCurrentProcess()
    if not kernel.GetProcessAffinityMask(current, ctypes.byref(affinity), ctypes.byref(system_affinity)):
        raise ctypes.WinError(ctypes.get_last_error())
    priority = kernel.GetPriorityClass(current)

    @ctypes.WINFUNCTYPE(wintypes.DWORD, ctypes.c_void_p)
    def harmless_thread(_argument):
        return 0

    ids = []
    for flags in (0, 4):  # 4 只隐藏调试器线程事件，不应隐藏 ETW 线程创建事件。
        handle = wintypes.HANDLE()
        status = ntdll.NtCreateThreadEx(
            ctypes.byref(handle), 0x1FFFFF, None, kernel.GetCurrentProcess(),
            ctypes.cast(harmless_thread, ctypes.c_void_p), None, flags, 0, 0, 0, None,
        )
        if status != 0:
            raise OSError(f"NtCreateThreadEx 失败：0x{status & 0xffffffff:08x}")
        try:
            tid = kernel.GetThreadId(handle)
            if not tid or kernel.WaitForSingleObject(handle, 4000) != 0:
                raise OSError("线程未按时结束或无法读取线程 ID。")
            ids.append(tid)
        finally:
            kernel.CloseHandle(handle)
    time.sleep(options.hold_ms / 1000)
    print(json.dumps({"pid": os.getpid(), "ordinary_tid": ids[0], "hidden_tid": ids[1],
                      "affinity": affinity.value, "priority": priority,
                      "started_monotonic": started, "finished_monotonic": time.monotonic()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
