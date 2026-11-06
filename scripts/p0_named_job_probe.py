"""普通权限创建自建作业；独立 UAC 辅助进程只为两个空作业设置工作集。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_elevated_ws_probe as ws
    from . import p0_job_probe as job
    from . import p0_sandbox_runtime as runtime
    from .p0_cpu_topology import read_windows_topology, select_mapping
else:
    import p0_appcontainer_probe as identity
    import p0_elevated_ws_probe as ws
    import p0_job_probe as job
    import p0_sandbox_runtime as runtime
    from p0_cpu_topology import read_windows_topology, select_mapping


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "outputs" / "p0_task3_named_job_20261105_01.jsonl"
HELPER_RECORD = ROOT / "outputs" / "p0_task3_named_job_helper_20261105_01.jsonl"
RECHECK_RECORD = ROOT / "outputs" / "p0_task3_named_job_20261105_02.jsonl"
RECHECK_HELPER_RECORD = ROOT / "outputs" / "p0_task3_named_job_helper_20261105_02.jsonl"
BASE_FLAGS = 0x0008 | 0x0010 | 0x0100 | 0x0200 | 0x2000


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("mask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("verb", wintypes.LPCWSTR), ("file", wintypes.LPCWSTR), ("parameters", wintypes.LPCWSTR),
                ("directory", wintypes.LPCWSTR), ("show", ctypes.c_int), ("instance", wintypes.HINSTANCE),
                ("idlist", ctypes.c_void_p), ("class_name", wintypes.LPCWSTR), ("class_key", wintypes.HKEY),
                ("hotkey", wintypes.DWORD), ("icon", wintypes.HANDLE), ("process", wintypes.HANDLE)]


def _names_valid(names: list[str]) -> bool:
    if type(names) is not list or len(names) != 2:
        return False
    pattern = r"Local\\P0Task3WS-([0-9a-f]{32})-(64|512)"
    found = [re.fullmatch(pattern, name) if isinstance(name, str) else None for name in names]
    return bool(all(found) and found[0].group(1) == found[1].group(1)
                and [item.group(2) for item in found] == ["64", "512"])


def _query_limits(kernel, handle) -> tuple[job.ExtendedLimits, job.Accounting]:
    limits, accounting = job.ExtendedLimits(), job.Accounting()
    for kind, value in ((9, limits), (1, accounting)):
        if not kernel.QueryInformationJobObject(handle, kind, ctypes.byref(value), ctypes.sizeof(value), None):
            raise ctypes.WinError(ctypes.get_last_error())
    return limits, accounting


def _expected(limits: job.ExtendedLimits, accounting: job.Accounting, logical: int, maximum: int | None) -> bool:
    flags = BASE_FLAGS | (0x0001 if maximum is not None else 0)
    return (limits.basic.flags == flags and limits.basic.active_limit == 1
            and limits.basic.affinity == 1 << logical and limits.process_memory == job.MEMORY_LIMIT
            and limits.job_memory == job.MEMORY_LIMIT and accounting.active_processes == 0
            and (maximum is None or (limits.basic.min_ws == 1024 * 1024 and limits.basic.max_ws == maximum)))


def _safe_to_continue(case: dict, limit_mib: int) -> bool:
    worker = case.get("worker", {})
    before, after = worker.get("before", {}), worker.get("after", {})
    limit = limit_mib * 1024 * 1024
    return (case.get("exit_code") == 0 and case.get("active_processes") == 0 and not case.get("error")
            and case.get("target_elevation") == 0 and case.get("target_elevation_type") == 3
            and case.get("target_user_matches") is True and case.get("is_appcontainer") is True
            and case.get("sid_matches") is True and case.get("capability_count") == 0
            and before.get("max") == after.get("max") == limit
            and bool(before.get("flags", 0) & 0x4) and bool(after.get("flags", 0) & 0x4)
            and worker.get("job_open_success") is False and worker.get("job_open_error") in (2, 5)
            and type(case.get("host_peak_after_exit")) is int and case["host_peak_after_exit"] <= job.MEMORY_LIMIT)


def _admin() -> bool:
    shell = ctypes.WinDLL("shell32")
    shell.IsUserAnAdmin.restype = ctypes.c_int
    return bool(shell.IsUserAnAdmin())


def helper(names: list[str], sink) -> dict:
    """只打开两个指定空作业；不创建进程或触碰账户策略。"""
    if not _names_valid(names) or not _admin():
        return {"passed": False, "error": "名称不合法或辅助进程未提升。"}
    kernel, _, advapi, _ = ws._apis()
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, ctypes.c_wchar_p]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    token = wintypes.HANDLE()
    result = {"passed": False, "jobs": []}
    try:
        binding = json.loads(ws.BINDING.read_bytes())
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["elevation"] = ws._u32(advapi, token, 20)
        result["user_matches"] = ws._token_user_hash(advapi, token) == binding.get("user_sid_sha256")
        if result["elevation"] != 1 or not result["user_matches"]:
            raise OSError("辅助进程不是指定用户的提升权限进程。")
        logical = select_mapping(*read_windows_topology())["workers"][0]["logical_processor"]
        for name, limit_mib in zip(names, (64, 512)):
            handle = kernel.OpenJobObjectW(0x0002 | 0x0004, False, name)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                limits, accounting = _query_limits(kernel, handle)
                if not _expected(limits, accounting, logical, None):
                    raise OSError("待配置作业不是预期的空测试作业。")
                limits.basic.flags |= 0x0001
                limits.basic.min_ws, limits.basic.max_ws = 1024 * 1024, limit_mib * 1024 * 1024
                if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                    raise ctypes.WinError(ctypes.get_last_error())
                verified, accounting = _query_limits(kernel, handle)
                if not _expected(verified, accounting, logical, limit_mib * 1024 * 1024):
                    raise OSError("测试作业的工作集配置回读失败。")
                item = {"name": name, "limit_mib": limit_mib, "verified": True}
                result["jobs"].append(item)
                sink({"event": "job_configured", **item})
            finally:
                kernel.CloseHandle(handle)
        result["passed"] = len(result["jobs"]) == 2
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if token:
            kernel.CloseHandle(token)
    return result


def _run_elevated_helper(names: list[str], recheck: bool = False) -> int:
    if not _names_valid(names) or ctypes.sizeof(ShellExecuteInfo) != 112:
        raise ValueError("辅助进程参数或本机结构布局不符合预期。")
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    info = ShellExecuteInfo()
    info.size, info.mask, info.verb, info.file = ctypes.sizeof(info), 0x40, "runas", sys.executable
    mode = "--helper-recheck" if recheck else "--helper"
    info.parameters = subprocess.list2cmdline(["-B", str(Path(__file__).resolve()), mode, *names])
    info.directory, info.show = str(ROOT), 0
    if not shell.ShellExecuteExW(ctypes.byref(info)) or not info.process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(info.process, 30000) != 0:
            raise OSError("UAC辅助进程未在30秒内退出。")
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(info.process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value
    finally:
        kernel.CloseHandle(info.process)


def run_probe(sink=None, recheck: bool = False) -> dict:
    if _admin():
        return {"passed": False, "error": "协调进程必须使用普通权限令牌。"}
    if sink is None:
        sink = lambda _event: None
    kernel, ntdll, advapi, userenv = ws._apis()
    jobs, sid = [], ctypes.c_void_p()
    result = {"passed": False, "scope": "只运行两个受控的非提升权限AppContainer进程。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        binding = json.loads(ws.BINDING.read_bytes())
        current_binding = ws.bind_current_user()
        if binding != current_binding:
            raise ValueError("普通用户或测试身份与绑定记录不一致。")
        profile = identity._recorded_profile(identity.PROFILE_RECORDS["P0Task3Probe_20261105_01"])
        manifest = json.loads(runtime.MANIFEST.read_bytes())
        destination = Path(profile["profile_folder"]) / identity.RUNTIME_DIR
        runtime._verify_resume_record(destination, manifest)
        result["verified_runtime_files"] = runtime._verify_copied(destination, manifest)
        if userenv.DeriveAppContainerSidFromAppContainerName(profile["profile_name"], ctypes.byref(sid)) != 0 or not sid:
            raise OSError("无法派生已授权测试身份。")
        helper_record = RECHECK_HELPER_RECORD if recheck else HELPER_RECORD
        output_version = "03" if recheck else "02"
        for path in (helper_record, ROOT / "outputs" / f"p0_task3_elevated_ws_child_64_20261105_{output_version}.txt",
                     ROOT / "outputs" / f"p0_task3_elevated_ws_child_512_20261105_{output_version}.txt"):
            if path.exists():
                raise FileExistsError(f"记录已存在，不覆盖：{path}")
        logical = select_mapping(*read_windows_topology())["workers"][0]["logical_processor"]
        nonce = uuid.uuid4().hex
        names = [f"Local\\P0Task3WS-{nonce}-{limit}" for limit in (64, 512)]
        if not _names_valid(names):
            raise ValueError("自建作业名称无效。")
        for name in names:
            ctypes.set_last_error(0)
            handle = kernel.CreateJobObjectW(None, name)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error() == 183:
                kernel.CloseHandle(handle)
                raise OSError("作业名称碰撞；不复用既有作业。")
            jobs.append(handle)
            limits = job.ExtendedLimits()
            limits.basic.flags, limits.basic.active_limit, limits.basic.affinity = BASE_FLAGS, 1, 1 << logical
            limits.process_memory = limits.job_memory = job.MEMORY_LIMIT
            if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not _expected(*_query_limits(kernel, handle), logical, None):
                raise OSError("普通权限作业初始化回读失败。")
        sink({"event": "owned_jobs_created", "names": names})
        result["helper_exit"] = _run_elevated_helper(names, recheck)
        if result["helper_exit"] != 0:
            raise OSError("UAC辅助进程未能配置两个测试作业。")
        helper_events = [json.loads(line) for line in helper_record.read_bytes().splitlines()]
        helper_results = [event.get("result", {}) for event in helper_events if event.get("event") == "result"]
        if (len(helper_results) != 1 or helper_results[0].get("passed") is not True
                or [item["name"] for item in helper_results[0].get("jobs", [])] != names):
            raise OSError("UAC辅助进程记录未能证明两个作业配置成功。")
        result["helper_record_sha256"] = hashlib.sha256(helper_record.read_bytes()).hexdigest()
        result["cases"] = []
        for handle, name, limit in zip(jobs, names, (64, 512)):
            resources = job._resource_gate()
            if not _expected(*_query_limits(kernel, handle), logical, limit * 1024 * 1024):
                raise OSError("执行前工作集配置回读不一致。")
            case = ws._case(kernel, ntdll, advapi, None, sid, profile, binding["user_sid_sha256"],
                            logical, limit, sink, preconfigured=handle, output_version=output_version, job_name=name)
            case["resource_precheck"] = resources
            result["cases"].append(case)
            sink({"event": "case", "result": case})
            if not case["passed"] and (not recheck or not _safe_to_continue(case, limit)):
                break
        result["passed"] = len(result["cases"]) == 2 and all(case["passed"] for case in result["cases"])
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if sid:
            advapi.FreeSid(sid)
        for handle in jobs:
            kernel.CloseHandle(handle)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="只对两个自建空作业执行一次UAC配置，再运行无害测试。")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--probe-recheck", action="store_true")
    mode.add_argument("--helper", nargs=2, metavar=("JOB64", "JOB512"))
    mode.add_argument("--helper-recheck", nargs=2, metavar=("JOB64", "JOB512"))
    options = parser.parse_args()
    helper_names = options.helper if options.helper is not None else options.helper_recheck
    recheck = options.probe_recheck or options.helper_recheck is not None
    record = (RECHECK_HELPER_RECORD if recheck else HELPER_RECORD) if helper_names is not None else (
        RECHECK_RECORD if recheck else RECORD)
    with record.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        sources = [Path(__file__), ROOT / "scripts" / "p0_elevated_ws_probe.py", ROOT / "scripts" / "p0_job_probe.py",
                   ROOT / "scripts" / "p0_job_probe_worker.py", ROOT / "scripts" / "p0_appcontainer_probe.py",
                   ROOT / "scripts" / "p0_sandbox_runtime.py",
                   runtime.MANIFEST, ws.BINDING]
        save({"event": "sources", "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                                for path in sources}})
        try:
            result = helper(helper_names, save) if helper_names is not None else run_probe(save, recheck)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
