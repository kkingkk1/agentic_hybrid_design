"""只核验探针进程现有权限与作业工作集设置；不更改用户或系统策略。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys

if __package__:
    from .p0_job_probe import ExtendedLimits, MEMORY_LIMIT, _apis
else:
    from p0_job_probe import ExtendedLimits, MEMORY_LIMIT, _apis


class Luid(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.LONG)]


class LuidAndAttributes(ctypes.Structure):
    _fields_ = [("luid", Luid), ("attributes", wintypes.DWORD)]


class TokenPrivileges(ctypes.Structure):
    _fields_ = [("count", wintypes.DWORD), ("privileges", LuidAndAttributes * 1)]


def _try_limits(kernel, include_working_set: bool) -> dict:
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        return {"success": False, "winerror": ctypes.get_last_error()}
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x0008 | 0x0010 | 0x0100 | 0x0200 | 0x2000
        limits.basic.active_limit = 1
        limits.basic.affinity = 1 << 16
        limits.process_memory = limits.job_memory = MEMORY_LIMIT
        if include_working_set:
            limits.basic.flags |= 0x0001
            limits.basic.min_ws, limits.basic.max_ws = 1024 * 1024, MEMORY_LIMIT
        ctypes.set_last_error(0)
        success = kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
        return {"success": bool(success), "winerror": 0 if success else ctypes.get_last_error()}
    finally:
        kernel.CloseHandle(handle)


def run_probe(privilege: str = "SeIncreaseWorkingSetPrivilege") -> dict:
    if privilege not in {"SeIncreaseWorkingSetPrivilege", "SeIncreaseBasePriorityPrivilege"}:
        raise ValueError("只允许检查与作业工作集有关的两个指定权限。")
    kernel, _ = _apis()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.LookupPrivilegeValueW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.POINTER(Luid)]
    advapi.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                              ctypes.POINTER(TokenPrivileges), wintypes.DWORD,
                                              ctypes.POINTER(TokenPrivileges), ctypes.POINTER(wintypes.DWORD)]
    advapi.AdjustTokenPrivileges.restype = wintypes.BOOL
    result = {"scope": "only this probe process; no user or system policy changes", "privilege": privilege,
              "baseline_limits": _try_limits(kernel, False),
              "working_set_without_adjustment": _try_limits(kernel, True)}
    token, luid = wintypes.HANDLE(), Luid()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x20 | 0x08, ctypes.byref(token)):
        result["open_token_error"] = ctypes.get_last_error()
        return result
    previous = TokenPrivileges()
    adjusted = False
    try:
        if not advapi.LookupPrivilegeValueW(None, privilege, ctypes.byref(luid)):
            result["lookup_error"] = ctypes.get_last_error()
            return result
        requested = TokenPrivileges(1, (LuidAndAttributes * 1)(LuidAndAttributes(luid, 2)))
        size = wintypes.DWORD()
        ctypes.set_last_error(0)
        ok = advapi.AdjustTokenPrivileges(token, False, ctypes.byref(requested), ctypes.sizeof(previous),
                                          ctypes.byref(previous), ctypes.byref(size))
        error = ctypes.get_last_error()
        result["adjust_success"] = bool(ok) and error == 0
        result["adjust_error"] = error
        if not result["adjust_success"]:
            return result
        adjusted = True
        result["working_set_with_existing_privilege"] = _try_limits(kernel, True)
    finally:
        if adjusted and previous.count:
            ctypes.set_last_error(0)
            restored = advapi.AdjustTokenPrivileges(token, False, ctypes.byref(previous), 0, None, None)
            result["restore_success"] = bool(restored) and ctypes.get_last_error() == 0
        elif adjusted:
            result["restore_success"] = True  # 原本已启用，没有状态变化。
        kernel.CloseHandle(token)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="只检查本进程现有权限，不修改账户或系统策略。")
    parser.add_argument("--privilege", choices=("SeIncreaseWorkingSetPrivilege", "SeIncreaseBasePriorityPrivilege"),
                        default="SeIncreaseWorkingSetPrivilege")
    parser.add_argument("--record", help="outputs 中新建 p0_task3_job_privilege_*.json，不得覆盖")
    options = parser.parse_args()
    if options.record and not re.fullmatch(r"p0_task3_job_privilege_[a-z0-9_]+\.json", options.record):
        parser.error("记录名须为 p0_task3_job_privilege_*.json，且不能包含路径。")
    if os.name != "nt":
        print(json.dumps({"error": "Windows only"}))
        return 1
    if options.record:
        path = Path(__file__).resolve().parents[1] / "outputs" / options.record
        with path.open("x", encoding="utf-8", newline="\n") as record:
            try:
                result = run_probe(options.privilege)
            except Exception as exc:
                result = {"error": f"{type(exc).__name__}: {exc}"}
            json.dump({"source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "result": result}, record, ensure_ascii=True, sort_keys=True)
    else:
        result = run_probe(options.privilege)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("restore_success", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
