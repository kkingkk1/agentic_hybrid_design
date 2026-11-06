"""仅验证受限 AppContainer 测试进程的作业工作集边界；不运行候选。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
    from . import p0_sandbox_runtime as runtime
    from .p0_job_probe_worker import MemoryCounters
    from .p0_cpu_topology import read_windows_topology, select_mapping
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job
    import p0_sandbox_runtime as runtime
    from p0_job_probe_worker import MemoryCounters
    from p0_cpu_topology import read_windows_topology, select_mapping


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "outputs" / "p0_task3_elevated_ws_20261105_01.jsonl"
BINDING = ROOT / "outputs" / "p0_task3_elevated_ws_user_binding_20261105_01.json"
WORKER = r'''import ctypes, json, mmap, sys, time
from ctypes import wintypes
from pathlib import Path
limit = int(sys.argv[1]) * 1024 * 1024
k = ctypes.WinDLL("kernel32", use_last_error=True)
p = ctypes.WinDLL("psapi", use_last_error=True)
k.GetCurrentProcess.restype = wintypes.HANDLE
k.GetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(wintypes.DWORD)]
k.SetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
class Counters(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in ("peak", "working", "paged_peak", "paged", "nonpaged_peak", "nonpaged", "pagefile", "pagefile_peak")]
p.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
h = k.GetCurrentProcess()
def current_limits():
    minimum, maximum, flags = ctypes.c_size_t(), ctypes.c_size_t(), wintypes.DWORD()
    if not k.GetProcessWorkingSetSizeEx(h, ctypes.byref(minimum), ctypes.byref(maximum), ctypes.byref(flags)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"min": minimum.value, "max": maximum.value, "flags": flags.value}
before = current_limits()
ctypes.set_last_error(0)
changed = bool(k.SetProcessWorkingSetSizeEx(h, 1024*1024, limit * 2, 0x8))
error = 0 if changed else ctypes.get_last_error()
after = current_limits()
job_open_success, job_open_error = None, None
if len(sys.argv) > 2:
    k.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, ctypes.c_wchar_p]
    k.OpenJobObjectW.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    ctypes.set_last_error(0)
    job_handle = k.OpenJobObjectW(0x0002, False, sys.argv[2])
    job_open_success = bool(job_handle)
    job_open_error = 0 if job_handle else ctypes.get_last_error()
    if job_handle: k.CloseHandle(job_handle)
views = []
mapped_bytes = 0
if limit == 64 * 1024 * 1024:
    allocation = bytearray(128 * 1024 * 1024)
    for offset in range(0, len(allocation), 4096):
        allocation[offset] = 1
else:
    path = Path(sys.executable).parent / "python313.dll"
    with path.open("rb") as source:
        for _ in range(95):
            view = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
            views.append(view)
            mapped_bytes += len(view)
            for offset in range(0, len(view), 4096):
                _ = view[offset]
counters = Counters()
counters.size = ctypes.sizeof(counters)
if not p.GetProcessMemoryInfo(h, ctypes.byref(counters), counters.size):
    raise ctypes.WinError(ctypes.get_last_error())
print("P0_WS_RESULT " + json.dumps({"limit": limit, "before": before, "disable_success": changed, "disable_error": error, "after": after, "job_open_success": job_open_success, "job_open_error": job_open_error, "mapped_views": len(views), "mapped_bytes": mapped_bytes, "peak_working_set": counters.peak, "working_set": counters.working}), flush=True)
time.sleep(0.05)
'''


def _u32(advapi, token, kind: int) -> int:
    value, length = wintypes.DWORD(), wintypes.DWORD()
    if not advapi.GetTokenInformation(token, kind, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.value


def _token_user_hash(advapi, token) -> str:
    length = wintypes.DWORD()
    advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(length))
    if not ctypes.sizeof(ctypes.c_void_p) <= length.value <= 65536:
        raise OSError("令牌用户SID信息长度无效。")
    data = ctypes.create_string_buffer(length.value)
    if not advapi.GetTokenInformation(token, 1, data, length.value, ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p)).contents.value
    if not sid:
        raise OSError("令牌缺少用户SID。")
    length_sid = advapi.GetLengthSid(sid)
    if not 8 <= length_sid <= 256:
        raise OSError("用户SID长度无效。")
    return hashlib.sha256(ctypes.string_at(sid, length_sid)).hexdigest()


def _worker_passed(result: dict, limit_mib: int) -> bool:
    worker = result.get("worker", {})
    before, after = worker.get("before", {}), worker.get("after", {})
    limit = limit_mib * 1024 * 1024
    job_handle_safe = (not result.get("job_name_tested") or
                       (worker.get("job_open_success") is False and worker.get("job_open_error") in (2, 5)))
    return (job_handle_safe and result.get("exit_code") == 0 and result.get("is_appcontainer") is True
            and result.get("sid_matches") is True and result.get("capability_count") == 0
            and result.get("target_elevation") == 0 and result.get("target_elevation_type") == 3
            and result.get("target_user_matches") is True
            and result.get("active_processes") == 0 and worker.get("limit") == limit
            and before.get("max") == limit and after.get("max") == limit
            and bool(before.get("flags", 0) & 0x4) and bool(after.get("flags", 0) & 0x4)
            and type(worker.get("disable_success")) is bool and type(before.get("min")) is int
            and before["min"] > 0 and before.get("min") == after.get("min")
            and type(result.get("host_peak_before_resume")) is int and result["host_peak_before_resume"] <= limit
            and type(result.get("host_peak_after_exit")) is int and result["host_peak_after_exit"] <= limit
            and (limit_mib != 512 or (worker.get("mapped_views") == 95
                                      and worker.get("mapped_bytes", 0) > limit))
            and type(worker.get("peak_working_set")) is int and worker["peak_working_set"] <= limit)


def _peak_working_set(process_handle) -> int:
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = MemoryCounters()
    counters.size = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(process_handle, ctypes.byref(counters), counters.size):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.peak_working_set


def _apis():
    kernel, ntdll = job._apis()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                                          ctypes.POINTER(ctypes.c_size_t)]
    kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                                  ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.CreateProcessW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p,
                                     wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, ctypes.c_wchar_p,
                                     ctypes.POINTER(identity.StartupInfoEx), ctypes.POINTER(identity.ProcessInfo)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    advapi.GetLengthSid.argtypes = [ctypes.c_void_p]
    advapi.GetLengthSid.restype = wintypes.DWORD
    advapi.FreeSid.argtypes = [ctypes.c_void_p]
    advapi.FreeSid.restype = ctypes.c_void_p
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    advapi.CreateProcessAsUserW.argtypes = [wintypes.HANDLE, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
                                             ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
                                             ctypes.c_wchar_p, ctypes.POINTER(identity.StartupInfoEx),
                                             ctypes.POINTER(identity.ProcessInfo)]
    advapi.CreateProcessAsUserW.restype = wintypes.BOOL
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    return kernel, ntdll, advapi, userenv


def _case(kernel, ntdll, advapi, linked, sid, profile: dict, expected_user: str,
          logical: int, limit_mib: int, sink, preconfigured=None, output_version: str = "01",
          job_name: str | None = None) -> dict:
    if output_version not in ("01", "02", "03"):
        raise ValueError("无效的测试输出版本。")
    result = {"limit_mib": limit_mib, "passed": False, "job_name_tested": job_name is not None}
    process, token = identity.ProcessInfo(), wintypes.HANDLE()
    handle, output, attributes = None, None, None
    initialized, resumed, completed, assigned = False, False, False, False
    diagnostic = ROOT / "outputs" / f"p0_task3_elevated_ws_child_{limit_mib}_20261105_{output_version}.txt"
    try:
        handle = preconfigured or kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = job.ExtendedLimits()
        limits.basic.flags = 0x0001 | 0x0008 | 0x0010 | 0x0100 | 0x0200 | 0x2000
        limits.basic.min_ws, limits.basic.max_ws = 1024 * 1024, limit_mib * 1024 * 1024
        limits.basic.active_limit, limits.basic.affinity = 1, 1 << logical
        limits.process_memory = limits.job_memory = job.MEMORY_LIMIT
        if preconfigured is None:
            if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
        queried = job.ExtendedLimits()
        if not kernel.QueryInformationJobObject(handle, 9, ctypes.byref(queried), ctypes.sizeof(queried), None):
            raise ctypes.WinError(ctypes.get_last_error())
        result["configured_flags"] = queried.basic.flags
        result["configured_max_ws"] = queried.basic.max_ws
        if queried.basic.flags & limits.basic.flags != limits.basic.flags or queried.basic.max_ws != limits.basic.max_ws:
            raise OSError("作业对象的工作集配置回读不一致。")
        output = diagnostic.open("xb", buffering=0)
        sink({"event": "child_output_created", "limit_mib": limit_mib, "path": str(diagnostic)})
        output_handle = msvcrt.get_osfhandle(output.fileno())
        os.set_handle_inheritable(output_handle, True)
        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        initialized = True
        caps = identity.SecurityCapabilities(sid, None, 0, 0)
        inherited = (wintypes.HANDLE * 1)(output_handle)
        for key, data, count in ((0x00020009, ctypes.byref(caps), ctypes.sizeof(caps)),
                                 (0x00020002, ctypes.byref(inherited), ctypes.sizeof(inherited))):
            if not kernel.UpdateProcThreadAttribute(attributes, 0, key, data, count, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        executable = Path(profile["profile_folder"]) / identity.RUNTIME_DIR / "python.exe"
        worker_arguments = [str(executable), "-I", "-B", "-c", WORKER, str(limit_mib)]
        if job_name is not None:
            worker_arguments.append(job_name)
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(worker_arguments))
        root = os.environ.get("SystemRoot", r"C:\Windows")
        environment = ctypes.create_unicode_buffer(identity._child_environment(root))
        startup = identity.StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.startup.flags = 0x00000100
        startup.startup.stdin = startup.startup.stdout = startup.startup.stderr = output_handle
        startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
        flags = 0x00080000 | 0x00000004 | 0x08000000 | 0x00000400 | 0x20
        started = time.monotonic()
        if linked is None:
            created = kernel.CreateProcessW(str(executable), command, None, None, True, flags, environment,
                                            os.path.join(root, "System32"), ctypes.byref(startup),
                                            ctypes.byref(process))
        else:
            created = advapi.CreateProcessAsUserW(linked, str(executable), command, None, None, True, flags,
                                                  environment, os.path.join(root, "System32"),
                                                  ctypes.byref(startup), ctypes.byref(process))
        if not created:
            raise ctypes.WinError(ctypes.get_last_error())
        result["pid"] = process.pid
        if not kernel.AssignProcessToJobObject(handle, process.process):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned = True
        if not advapi.OpenProcessToken(process.process, 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        result.update({"target_elevation_type": _u32(advapi, token, 18), "target_elevation": _u32(advapi, token, 20),
                       "is_appcontainer": bool(_u32(advapi, token, 29)),
                       "target_user_matches": _token_user_hash(advapi, token) == expected_user})
        length = wintypes.DWORD()
        advapi.GetTokenInformation(token, 31, None, 0, ctypes.byref(length))
        if not ctypes.sizeof(ctypes.c_void_p) <= length.value <= 65536:
            raise OSError("目标身份SID信息长度无效。")
        sid_info = ctypes.create_string_buffer(length.value)
        if not advapi.GetTokenInformation(token, 31, sid_info, length.value, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        target_sid = ctypes.cast(sid_info, ctypes.POINTER(ctypes.c_void_p)).contents.value
        advapi.GetTokenInformation(token, 30, None, 0, ctypes.byref(length))
        if not 4 <= length.value <= 65536:
            raise OSError("目标capability信息长度无效。")
        capabilities = ctypes.create_string_buffer(length.value)
        if not advapi.GetTokenInformation(token, 30, capabilities, length.value, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        result.update({"sid_matches": bool(advapi.EqualSid(sid, target_sid)),
                       "capability_count": ctypes.cast(capabilities, ctypes.POINTER(wintypes.DWORD)).contents.value})
        if (result["target_elevation"] != 0 or result["target_elevation_type"] != 3
                or not result["target_user_matches"] or not result["is_appcontainer"]
                or not result["sid_matches"] or result["capability_count"] != 0):
            raise OSError("目标不是预期的非提升权限AppContainer；保持挂起并停止。")
        result["host_peak_before_resume"] = _peak_working_set(process.process)
        if ntdll.NtResumeProcess(process.process) != 0:
            raise OSError("无法恢复受控测试进程。")
        resumed = True
        result["host_observed_peak"] = result["host_peak_before_resume"]
        while True:
            remaining = max(0, int((15 - (time.monotonic() - started)) * 1000))
            wait = kernel.WaitForSingleObject(process.process, min(remaining, 10))
            peak = _peak_working_set(process.process)
            result["host_observed_peak"] = max(result["host_observed_peak"], peak)
            result["elapsed_seconds"] = time.monotonic() - started
            if peak > job.MEMORY_LIMIT:
                result["violation"] = "working_set_over_512_mib"
                raise OSError("宿主观察到工作集峰值超过512 MiB，终止测试。")
            if wait == 0:
                if result["elapsed_seconds"] > 15:
                    raise OSError("受控测试进程在时限后结束。")
                break
            if wait != 258 or result["elapsed_seconds"] >= 15:
                raise OSError("受控测试进程超过15秒或等待失败。")
        completed = True
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["exit_code"] = code.value
        result["host_peak_after_exit"] = _peak_working_set(process.process)
        output.close()
        if diagnostic.stat().st_size > job.STDOUT_LIMIT:
            raise OSError("受控测试输出超过限制。")
        lines = diagnostic.read_bytes().decode("utf-8", errors="replace").splitlines()
        markers = [line.removeprefix("P0_WS_RESULT ") for line in lines if line.startswith("P0_WS_RESULT ")]
        if len(markers) != 1:
            raise OSError("未收到唯一的工作集测试结果。")
        result["worker"] = json.loads(markers[0])
    except (OSError, ValueError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if handle and process.process and not completed:
            if assigned:
                kernel.TerminateJobObject(handle, 1)
            else:
                kernel.TerminateProcess(process.process, 1)
            kernel.WaitForSingleObject(process.process, 5000)
        if handle:
            accounting = job.Accounting()
            idle_deadline = time.monotonic() + 3
            while kernel.QueryInformationJobObject(handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                result["active_processes"] = accounting.active_processes
                result["cpu_seconds"] = (accounting.user + accounting.kernel) / 10_000_000
                if accounting.active_processes == 0 or time.monotonic() >= idle_deadline:
                    break
                time.sleep(0.01)
            if preconfigured is None:
                kernel.CloseHandle(handle)
        if token:
            kernel.CloseHandle(token)
        if process.thread:
            kernel.CloseHandle(process.thread)
        if process.process:
            kernel.CloseHandle(process.process)
        if initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        if output is not None:
            output.close()
        result["resumed"] = resumed
    result["passed"] = _worker_passed(result, limit_mib) and not result.get("error")
    return result


def bind_current_user() -> dict:
    shell = ctypes.WinDLL("shell32")
    shell.IsUserAnAdmin.restype = ctypes.c_int
    if shell.IsUserAnAdmin():
        raise OSError("用户绑定只能从普通权限进程创建。")
    kernel, _, advapi, _ = _apis()
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        if _u32(advapi, token, 18) != 3 or _u32(advapi, token, 20) != 0:
            raise OSError("当前令牌不是预期的普通权限关联令牌。")
        profile = identity._recorded_profile(identity.PROFILE_RECORDS["P0Task3Probe_20261105_01"])
        return {"user_sid_sha256": _token_user_hash(advapi, token),
                "profile_record_sha256": profile["source_record_sha256"], "non_elevated": True}
    finally:
        if token:
            kernel.CloseHandle(token)


def run_probe(sink=None) -> dict:
    shell = ctypes.WinDLL("shell32")
    shell.IsUserAnAdmin.restype = ctypes.c_int
    if not shell.IsUserAnAdmin():
        return {"passed": False, "error": "当前令牌未提升；不启动工作集组合探针。"}
    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "scope": "仅测试64和512 MiB下的自建非提升权限AppContainer进程。"}
    kernel, ntdll, advapi, userenv = _apis()
    current, linked, sid = wintypes.HANDLE(), wintypes.HANDLE(), ctypes.c_void_p()
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(identity.PROFILE_RECORDS["P0Task3Probe_20261105_01"])
        binding = json.loads(BINDING.read_bytes())
        if (binding.get("non_elevated") is not True
                or binding.get("profile_record_sha256") != profile["source_record_sha256"]
                or not isinstance(binding.get("user_sid_sha256"), str)):
            raise ValueError("普通用户绑定记录不匹配。")
        manifest = json.loads(runtime.MANIFEST.read_bytes())
        destination = Path(profile["profile_folder"]) / identity.RUNTIME_DIR
        runtime._verify_resume_record(destination, manifest)
        result["verified_runtime_files"] = runtime._verify_copied(destination, manifest)
        if userenv.DeriveAppContainerSidFromAppContainerName(profile["profile_name"], ctypes.byref(sid)) != 0 or not sid:
            raise OSError("无法派生已授权测试身份。")
        sid_string = ctypes.c_wchar_p()
        try:
            if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
                raise ctypes.WinError(ctypes.get_last_error())
            if sid_string.value != profile["profile_sid"]:
                raise OSError("派生身份与已授权创建记录不一致。")
        finally:
            if sid_string:
                kernel.LocalFree(ctypes.cast(sid_string, ctypes.c_void_p))
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(current)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["monitor_elevation_type"] = _u32(advapi, current, 18)
        result["monitor_elevation"] = _u32(advapi, current, 20)
        if result["monitor_elevation_type"] != 2 or result["monitor_elevation"] != 1:
            raise OSError("当前令牌不是预期的提升权限令牌。")
        length = wintypes.DWORD()
        if not advapi.GetTokenInformation(current, 19, ctypes.byref(linked), ctypes.sizeof(linked), ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["linked_elevation_type"] = _u32(advapi, linked, 18)
        result["linked_elevation"] = _u32(advapi, linked, 20)
        result["linked_user_matches"] = _token_user_hash(advapi, linked) == binding["user_sid_sha256"]
        if result["linked_elevation_type"] != 3 or result["linked_elevation"] != 0 or not result["linked_user_matches"]:
            raise OSError("关联令牌不是预期的普通权限令牌。")
        slots = select_mapping(*read_windows_topology())["workers"]
        result["cases"] = []
        for limit in (64, 512):
            resources = job._resource_gate()
            case = _case(kernel, ntdll, advapi, linked, sid, profile, binding["user_sid_sha256"],
                         slots[0]["logical_processor"], limit, sink)
            case["resource_precheck"] = resources
            result["cases"].append(case)
            sink({"event": "case", "result": case})
            if not case["passed"]:
                break
        result["passed"] = len(result["cases"]) == 2 and all(case["passed"] for case in result["cases"])
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if sid:
            advapi.FreeSid(sid)
        if linked:
            kernel.CloseHandle(linked)
        if current:
            kernel.CloseHandle(current)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="仅验证自建测试进程的作业工作集限制，不运行候选。")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="新建固定任务3记录文件，不覆盖")
    mode.add_argument("--bind-user", action="store_true", help="只记录当前普通用户SID的哈希")
    options = parser.parse_args()
    if options.bind_user:
        binding = bind_current_user()
        with BINDING.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(binding, stream, ensure_ascii=True, sort_keys=True)
        print(json.dumps({"bound": True, "record": str(BINDING)}))
        return 0
    with RECORD.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        sources = [Path(__file__), ROOT / "scripts" / "p0_job_probe.py", ROOT / "scripts" / "p0_appcontainer_probe.py",
                   ROOT / "scripts" / "p0_sandbox_runtime.py", runtime.MANIFEST, BINDING]
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
