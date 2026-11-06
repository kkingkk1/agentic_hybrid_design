"""测试自建进程能否设置和绕过单进程工作集硬上限；不运行候选。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_probe() -> dict:
    if os.name != "nt":
        raise OSError("工作集探针只支持 Windows。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel.SetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.c_size_t,
                                                   ctypes.c_size_t, wintypes.DWORD]
    kernel.SetProcessWorkingSetSizeEx.restype = wintypes.BOOL
    kernel.GetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                                   ctypes.POINTER(ctypes.c_size_t),
                                                   ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessWorkingSetSizeEx.restype = wintypes.BOOL
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    result = {"passed": False, "scope": "controlled probe process only; no system policy change"}
    process = subprocess.Popen(
        [sys.executable, "-I", "-B", str(ROOT / "scripts" / "p0_job_probe_worker.py"), "working_set"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW | subprocess.NORMAL_PRIORITY_CLASS,
    )
    try:
        ctypes.set_last_error(0)
        configured = kernel.SetProcessWorkingSetSizeEx(int(process._handle), 1024 * 1024,
                                                       512 * 1024 * 1024, 0x4)
        result["set_success"] = bool(configured)
        result["set_error"] = 0 if configured else ctypes.get_last_error()
        if not configured:
            return result
        minimum, maximum, flags = ctypes.c_size_t(), ctypes.c_size_t(), wintypes.DWORD()
        if not kernel.GetProcessWorkingSetSizeEx(int(process._handle), ctypes.byref(minimum),
                                                 ctypes.byref(maximum), ctypes.byref(flags)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["configured_maximum_bytes"] = maximum.value
        result["configured_flags"] = flags.value
        if ntdll.NtResumeProcess(int(process._handle)) != 0:
            raise OSError("无法恢复自建工作集探针。")
        stdout, stderr = process.communicate(timeout=5)
        result["worker_exit"] = process.returncode
        result["worker_stderr"] = stderr.decode("utf-8", errors="replace")[:1024]
        if process.returncode == 0:
            result["worker"] = json.loads(stdout)
            result["passed"] = (maximum.value == 512 * 1024 * 1024 and bool(flags.value & 0x4)
                                and not result["worker"]["disable_success"]
                                and bool(result["worker"]["after_flags"] & 0x4))
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def main() -> int:
    try:
        result = run_probe()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"passed": False, "error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
