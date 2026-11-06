"""仅用固定的无害进程核验 AppContainer 身份，保留显式创建的配置。"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_FIXTURE = ROOT / "outputs" / "p0_task3_boundary_fake_sensitive_20261105_01.txt"
OWN_FIXTURE_NAME = "p0_task3_own_fake_20261105_01.txt"
RUNTIME_DIR = "p0_runtime_20261105_01"
PYTHON_DIAGNOSTIC = ROOT / "outputs" / "p0_task3_python_version_diagnostic_20261105_01.txt"
PROFILE_RECORDS = {
    "P0Task3Probe_20261105_01": "p0_task3_appcontainer_profile_20261105_01.jsonl",
    "P0Task3Probe_20261105_02": "p0_task3_appcontainer_profile_20261105_02.jsonl",
}

# 固定的无害代码：语法编译不执行源码，并检查作业内不能创建第二个进程。
COMBINED_PROBE_CODE = '''
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys

compile("raise RuntimeError('must not execute')", "p0_fixture.py", "exec")
try:
    compile("not valid python !", "p0_invalid_fixture.py", "exec")
except SyntaxError:
    invalid_rejected = True
else:
    invalid_rejected = False

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]
kernel.GetPriorityClass.restype = wintypes.DWORD
kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                           ctypes.POINTER(ctypes.c_size_t)]
kernel.GetProcessAffinityMask.restype = wintypes.BOOL
process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask),
                                     ctypes.byref(system_mask)):
    raise ctypes.WinError(ctypes.get_last_error())
try:
    child = subprocess.Popen([sys.executable, "-I", "-B", "-c", "pass"])
except OSError as exc:
    child_error = getattr(exc, "winerror", None)
else:
    child.kill()
    child.wait(timeout=5)
    child_error = None
print("P0_COMBINED_OK " + json.dumps({"pid": os.getpid(), "affinity": process_mask.value,
                                      "priority": kernel.GetPriorityClass(kernel.GetCurrentProcess()),
                                      "child_error": child_error, "invalid_rejected": invalid_rejected}))
'''
JOB_PROBE_ACTIONS = {"owned_python_job", "owned_python_job_timeout"}


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR), ("desktop", wintypes.LPWSTR),
                ("title", wintypes.LPWSTR), ("x", wintypes.DWORD), ("y", wintypes.DWORD),
                ("x_size", wintypes.DWORD), ("y_size", wintypes.DWORD),
                ("x_chars", wintypes.DWORD), ("y_chars", wintypes.DWORD),
                ("fill", wintypes.DWORD), ("flags", wintypes.DWORD), ("show", wintypes.WORD),
                ("reserved_size", wintypes.WORD), ("reserved2", ctypes.c_void_p),
                ("stdin", wintypes.HANDLE), ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]


class SecurityCapabilities(ctypes.Structure):
    _fields_ = [("appcontainer_sid", ctypes.c_void_p), ("capabilities", ctypes.c_void_p),
                ("capability_count", wintypes.DWORD), ("reserved", wintypes.DWORD)]


def _recorded_profile(record_name: str) -> dict:
    """只接受先前完整记录的本项目配置；不发现或复用其他配置。"""
    if not re.fullmatch(r"p0_task3_appcontainer_[a-z0-9_]+\.jsonl", record_name):
        raise ValueError("身份来源须是 outputs 下的任务3记录文件名。")
    raw = (Path(__file__).resolve().parents[1] / "outputs" / record_name).read_bytes()
    if len(raw) > 65536:
        raise ValueError("身份来源记录过大。")
    events = [json.loads(line) for line in raw.splitlines()]
    if [item.get("event") for item in events] != ["source", "profile_create_attempt", "profile_created",
                                                   "profile_details", "result"]:
        raise ValueError("身份来源记录不完整。")
    attempt, created, details, result = events[1], events[2], events[3], events[4].get("result", {})
    name = details.get("profile_name")
    if (not isinstance(name, str) or not re.fullmatch(r"P0Task3Probe_[0-9]{8}_[0-9]{2}", name)
            or attempt.get("profile_name") != name or created.get("profile_name") != name
            or result.get("profile_name") != name or result.get("profile_created") is not True
            or not isinstance(details.get("profile_sid"), str) or not isinstance(details.get("profile_folder"), str)
            or result.get("profile_sid") != details["profile_sid"]
            or result.get("profile_folder") != details["profile_folder"]):
        raise ValueError("身份来源记录不一致。")
    return {"profile_name": name, "profile_sid": details["profile_sid"],
            "profile_folder": details["profile_folder"], "source_record": record_name,
            "source_record_sha256": hashlib.sha256(raw).hexdigest()}


def _child_environment(system_root: str) -> str:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        raise OSError("缺少 LOCALAPPDATA，无法定位 AppContainer 配置目录。")
    values = {"LOCALAPPDATA": local_appdata, "PATH": os.path.join(system_root, "System32"),
              "SystemRoot": system_root, "WINDIR": system_root}
    return "\0".join(f"{name}={value}" for name, value in values.items()) + "\0\0"


def _lpac_mode_acceptable(requested: bool, observed: bool | None) -> bool:
    # 普通身份验证不依赖 LPAC；要求 LPAC 时必须得到肯定的实测结果。
    return (observed is None and not requested) or (observed is not None and observed == requested)


def _controlled_command(system_dir: str, action: str, port: int | None = None,
                        profile: dict | None = None) -> tuple[str, str]:
    """只拼装固定无害探针；没有候选程序、任意路径或网络目标入口。"""
    executable = os.path.join(system_dir, "cmd.exe")
    if action == "identity" and port is None:
        return executable, subprocess.list2cmdline([executable, "/d", "/c", "exit", "0"])
    if action in {"fixture", "own_fixture", "other_fixture"} and port is None:
        if action in {"own_fixture", "other_fixture"}:
            name = profile.get("profile_name") if isinstance(profile, dict) else None
            if name not in PROFILE_RECORDS:
                raise ValueError("自己的模拟文件仅允许指定的测试身份访问。")
            recorded = _recorded_profile(PROFILE_RECORDS[name])
            if (profile.get("profile_sid") != recorded["profile_sid"]
                    or os.path.normcase(profile.get("profile_folder", ""))
                    != os.path.normcase(recorded["profile_folder"])):
                raise ValueError("身份与模拟文件来源不一致。")
            target = recorded
            if action == "other_fixture":
                other = next(candidate for candidate in PROFILE_RECORDS if candidate != name)
                target = _recorded_profile(PROFILE_RECORDS[other])
                if target["profile_name"] != other or target["profile_sid"] == recorded["profile_sid"]:
                    raise ValueError("目标模拟文件的身份不匹配或不独立。")
            path = str(Path(target["profile_folder"]) / OWN_FIXTURE_NAME)
        else:
            path = str(BOUNDARY_FIXTURE)
        if not re.fullmatch(r"[a-zA-Z0-9_:\\. /-]+", path):
            raise ValueError("模拟文件路径包含不支持的字符。")
        command = f'type "{path}"'
    elif action == "output_control" and port is None:
        command = "echo P0_OUTPUT_CONTROL"
    elif action == "curl_version" and port is None:
        command = "curl.exe --version"
    elif action == "python_version" and port is None:
        python = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python313" / "python.exe"
        if (os.path.normcase(os.path.normpath(sys.executable)) != os.path.normcase(os.path.normpath(python))
                or not re.fullmatch(r"[a-zA-Z0-9_:\\./-]+", str(python))):
            raise ValueError("当前解释器不是本机已选定的 Python 3.13 路径。")
        command = f'"{python}" -I -B -V'
    elif action in {"owned_python_smoke", "owned_python_smoke_retry", "owned_python_direct",
                    "owned_python_direct_recheck", "owned_python_direct_recheck2", *JOB_PROBE_ACTIONS} and port is None:
        name = profile.get("profile_name") if isinstance(profile, dict) else None
        if name not in PROFILE_RECORDS:
            raise ValueError("运行时探针只能使用指定测试身份。")
        recorded = _recorded_profile(PROFILE_RECORDS[name])
        if (profile.get("profile_sid") != recorded["profile_sid"]
                or os.path.normcase(profile.get("profile_folder", ""))
                != os.path.normcase(recorded["profile_folder"])):
            raise ValueError("运行时身份与创建记录不一致。")
        python = Path(recorded["profile_folder"]) / RUNTIME_DIR / "python.exe"
        if not re.fullmatch(r"[a-zA-Z0-9_:\\./-]+", str(python)):
            raise ValueError("运行时路径包含不支持的字符。")
        imports = ("import json, math, random, decimal, ctypes, ssl, sqlite3, sys; "
                   "print('P0_RUNTIME_OK ' + json.dumps({'version': list(sys.version_info[:3]), "
                   "'executable': sys.executable, 'origins': {m.__name__: m.__spec__.origin for m in "
                   "(json, math, random, decimal, ctypes, ssl, sqlite3)}}))")
        if action in {"owned_python_direct", "owned_python_direct_recheck", "owned_python_direct_recheck2",
                      *JOB_PROBE_ACTIONS}:
            code = (COMBINED_PROBE_CODE if action == "owned_python_job" else
                    "import time; time.sleep(30)" if action == "owned_python_job_timeout" else imports)
            return str(python), subprocess.list2cmdline([str(python), "-I", "-B", "-c", code])
        # 此路径已限制为不含空格和 shell 特殊字符；不要给首个参数加引号。
        command = f'{python} -I -B -c "{imports}"'
    elif action == "loopback" and type(port) is int and 0 < port <= 65535:
        command = f"curl.exe --silent --noproxy * --max-time 3 http://127.0.0.1:{port}/p0"
    else:
        raise ValueError("只允许预定义的身份、模拟文件和回环探针。")
    return executable, f'"{executable}" /d /c {command}'


def _runtime_evidence(output: str, profile: dict) -> dict:
    markers = [line.removeprefix("P0_RUNTIME_OK ") for line in output.splitlines()
               if line.startswith("P0_RUNTIME_OK ")]
    if len(markers) != 1:
        return {"passed": False, "error": "缺少唯一运行时自检结果。"}
    try:
        report = json.loads(markers[0])
        runtime = os.path.normcase(os.path.normpath(Path(profile["profile_folder"]) / RUNTIME_DIR))
        expected_executable = os.path.normcase(os.path.normpath(Path(runtime) / "python.exe"))
        modules = {"json", "math", "random", "decimal", "ctypes", "ssl", "sqlite3"}
        origins = report.get("origins", {})
        origin_checks = (isinstance(origins, dict) and set(origins) == modules and all(
            isinstance(path, str) and ((name == "math" and path == "built-in")
                                       or os.path.commonpath([runtime, os.path.normcase(os.path.normpath(path))])
                                       == runtime) for name, path in origins.items()))
        passed = (report.get("version") == [3, 13, 12]
                  and os.path.normcase(os.path.normpath(report.get("executable", ""))) == expected_executable
                  and origin_checks)
        return {"passed": passed, "report": report}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"}


def _combined_evidence(output: str, pid: int, expected_affinity: int) -> dict:
    markers = [line.removeprefix("P0_COMBINED_OK ") for line in output.splitlines()
               if line.startswith("P0_COMBINED_OK ")]
    if len(markers) != 1:
        return {"passed": False, "error": "缺少唯一组合探针结果。"}
    try:
        report = json.loads(markers[0])
        passed = (type(report) is dict and report.get("pid") == pid
                  and report.get("affinity") == expected_affinity
                  and report.get("priority") == 0x20
                  and report.get("child_error") == 1816 and report.get("invalid_rejected") is True)
        return {"passed": passed, "report": report}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"}


def run_probe(lpac: bool = False, control: bool = False, profile_name: str | None = None, sink=None,
              reused_profile: dict | None = None, action: str = "identity", port: int | None = None) -> dict:
    """只启动固定的 cmd /c exit 0；显式创建的配置保留，不自动删除。"""
    if os.name != "nt" or (ctypes.sizeof(StartupInfoEx), ctypes.sizeof(ProcessInfo),
                            ctypes.sizeof(SecurityCapabilities)) != (112, 24, 24):
        raise OSError("身份探针仅支持核验过结构布局的 64 位 Windows。")
    if profile_name and (lpac or control or not re.fullmatch(r"P0Task3Probe_[0-9]{8}_[0-9]{2}", profile_name)):
        raise ValueError("配置名称或探针模式无效。")
    if reused_profile and (profile_name or lpac or control):
        raise ValueError("重试配置不能与其他身份模式混用。")
    if action != "identity" and not reused_profile:
        raise ValueError("边界探针只允许使用本项目创建记录中的身份。")
    if sink is None:
        sink = lambda _event: None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [ctypes.c_wchar_p,
                                                                  ctypes.POINTER(ctypes.c_void_p)]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    userenv.CreateAppContainerProfile.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                                  ctypes.c_void_p, wintypes.DWORD,
                                                  ctypes.POINTER(ctypes.c_void_p)]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.GetAppContainerFolderPath.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_wchar_p)]
    userenv.GetAppContainerFolderPath.restype = ctypes.c_long
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    ole = ctypes.WinDLL("ole32")
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    advapi.FreeSid.argtypes = [ctypes.c_void_p]
    advapi.FreeSid.restype = ctypes.c_void_p
    advapi.GetLengthSid.argtypes = [ctypes.c_void_p]
    advapi.GetLengthSid.restype = wintypes.DWORD
    advapi.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    advapi.EqualSid.restype = wintypes.BOOL
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                          wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    kernel.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                                  ctypes.c_void_p, ctypes.c_size_t,
                                                  ctypes.c_void_p, ctypes.c_void_p]
    kernel.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel.CreateProcessW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p,
                                     ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
                                     ctypes.c_wchar_p, ctypes.POINTER(StartupInfoEx), ctypes.POINTER(ProcessInfo)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long

    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "lpac_requested": lpac, "control": control,
              "profile_created": False, "action": action}
    sid, token, process = ctypes.c_void_p(), wintypes.HANDLE(), ProcessInfo()
    attributes_initialized = False
    attributes = None
    completed = False
    boundary_job = None
    output_sink = None
    stderr_sink = None
    input_sink = None
    diagnostic_path = None
    stderr_path = None
    try:
        if profile_name:
            result["stage"] = "create_profile"
            result["profile_name"] = profile_name
            sink({"event": "profile_create_attempt", "profile_name": profile_name})
            status = userenv.CreateAppContainerProfile(profile_name, profile_name, "P0 controlled identity probe",
                                                        None, 0, ctypes.byref(sid))
            result["create_profile_status"] = status & 0xffffffff
            if status != 0 or not sid:
                raise OSError("无法新建指定配置；不会复用已有配置。")
            result["profile_created"] = True
            sink({"event": "profile_created", "profile_name": profile_name})
        else:
            result["stage"] = "derive_sid"
            name = reused_profile["profile_name"] if reused_profile else "P0Probe." + uuid.uuid4().hex
            status = userenv.DeriveAppContainerSidFromAppContainerName(name, ctypes.byref(sid))
            result["derive_status"] = status & 0xffffffff
            if status != 0 or not sid:
                raise OSError("无法为本次探针派生 AppContainer SID。")
            if reused_profile:
                result.update({"profile_name": name, "profile_reused": True,
                               "source_record": reused_profile["source_record"],
                               "source_record_sha256": reused_profile["source_record_sha256"]})
        if profile_name or reused_profile:
            sid_string, folder = ctypes.c_wchar_p(), ctypes.c_wchar_p()
            try:
                if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
                    raise ctypes.WinError(ctypes.get_last_error())
                result["profile_sid"] = sid_string.value
                folder_status = userenv.GetAppContainerFolderPath(sid_string, ctypes.byref(folder))
                result["folder_status"] = folder_status & 0xffffffff
                if folder_status != 0 or not folder.value:
                    raise OSError("配置已创建，但无法确定其目录；保留配置并停止。")
                result["profile_folder"] = folder.value
                if reused_profile and (sid_string.value != reused_profile["profile_sid"]
                        or os.path.normcase(os.path.normpath(folder.value))
                        != os.path.normcase(os.path.normpath(reused_profile["profile_folder"]))):
                    raise OSError("现有身份与创建记录不一致；停止重试。")
                sink({"event": "profile_details" if profile_name else "profile_verified",
                      "profile_name": profile_name or reused_profile["profile_name"],
                      "profile_sid": sid_string.value, "profile_folder": folder.value})
            finally:
                if folder:
                    ole.CoTaskMemFree(ctypes.cast(folder, ctypes.c_void_p))
                if sid_string:
                    kernel.LocalFree(ctypes.cast(sid_string, ctypes.c_void_p))
        result["sid_sha256"] = hashlib.sha256(ctypes.string_at(sid, advapi.GetLengthSid(sid))).hexdigest()

        result["stage"] = "initialize_attributes"
        size = ctypes.c_size_t()
        count = 1 + int(lpac) + int(action != "identity")
        kernel.InitializeProcThreadAttributeList(None, count, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attributes, count, 0, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        attributes_initialized = True
        result["stage"] = "configure_security_capabilities"
        caps = SecurityCapabilities(sid, None, 0, 0)
        if not control and not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020009, ctypes.byref(caps),
                                                                ctypes.sizeof(caps), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        policy = wintypes.DWORD(1)
        if lpac and not kernel.UpdateProcThreadAttribute(attributes, 0, 0x0002000F, ctypes.byref(policy),
                                                         ctypes.sizeof(policy), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        if action != "identity":
            # 只继承宿主新开的限定输出句柄，不依赖容器打开设备或继承其他句柄。
            if action == "python_version":
                diagnostic_path = PYTHON_DIAGNOSTIC
            elif action in {"owned_python_smoke", "owned_python_smoke_retry", "owned_python_direct",
                            "owned_python_direct_recheck", "owned_python_direct_recheck2", *JOB_PROBE_ACTIONS}:
                if reused_profile["profile_name"] not in PROFILE_RECORDS:
                    raise ValueError("无效的运行时测试身份。")
                if action == "owned_python_smoke_retry" and reused_profile["profile_name"] != "P0Task3Probe_20261105_01":
                    raise ValueError("只允许重试第一个身份的已验证运行时。")
                suffix = reused_profile["profile_name"][-2:]
                if action in JOB_PROBE_ACTIONS:
                    output_id = uuid.uuid4().hex
                    diagnostic_path = ROOT / "outputs" / f"p0_task3_combined_{output_id}_stdout.txt"
                    stderr_path = ROOT / "outputs" / f"p0_task3_combined_{output_id}_stderr.txt"
                elif action in {"owned_python_direct", "owned_python_direct_recheck", "owned_python_direct_recheck2"}:
                    version = {"owned_python_direct": "01", "owned_python_direct_recheck": "02",
                               "owned_python_direct_recheck2": "03"}[action]
                    diagnostic_path = ROOT / "outputs" / f"p0_task3_runtime_direct_{suffix}_20261105_{version}.txt"
                else:
                    version = "02" if action == "owned_python_smoke_retry" else "01"
                    diagnostic_path = ROOT / "outputs" / f"p0_task3_runtime_smoke_{suffix}_20261105_{version}.txt"
            output_sink = (diagnostic_path.open("xb", buffering=0) if diagnostic_path is not None
                           else open(os.devnull, "r+b", buffering=0))
            output_handle = msvcrt.get_osfhandle(output_sink.fileno())
            if action in JOB_PROBE_ACTIONS:
                stderr_sink = stderr_path.open("xb", buffering=0)
                input_sink = open(os.devnull, "r+b", buffering=0)
                input_handle = msvcrt.get_osfhandle(input_sink.fileno())
                stderr_handle = msvcrt.get_osfhandle(stderr_sink.fileno())
                handles = (input_handle, output_handle, stderr_handle)
            else:
                input_handle = stderr_handle = output_handle
                handles = (output_handle,)
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            inherited = (wintypes.HANDLE * len(handles))(*handles)
            if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020002, ctypes.byref(inherited),
                                                    ctypes.sizeof(inherited), None, None):
                raise ctypes.WinError(ctypes.get_last_error())

        root = os.environ.get("SystemRoot", r"C:\Windows")
        system_dir = os.path.join(root, "System32")
        executable, command_line = _controlled_command(system_dir, action, port, reused_profile)
        result["executable_exists"] = os.path.isfile(executable)
        command = ctypes.create_unicode_buffer(command_line)
        # 仅传 Windows 必需的目录变量，不继承账号、代理或凭证环境变量。
        environment = ctypes.create_unicode_buffer(_child_environment(root))
        startup = StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        if output_sink is not None:
            startup.startup.flags = 0x00000100
            startup.startup.stdin = input_handle
            startup.startup.stdout = output_handle
            startup.startup.stderr = stderr_handle
        startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
        flags = 0x00080000 | 0x00000004 | 0x08000000 | 0x00000400
        if action in JOB_PROBE_ACTIONS:
            flags |= subprocess.NORMAL_PRIORITY_CLASS
        result["stage"] = "create_suspended_process"
        started = time.monotonic()
        if not kernel.CreateProcessW(executable, command, None, None, output_sink is not None, flags, environment,
                                     system_dir, ctypes.byref(startup), ctypes.byref(process)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["pid"] = process.pid
        if action != "identity":
            if __package__:
                from . import p0_job_probe as job
            else:
                import p0_job_probe as job
            job_kernel, _ = job._apis()
            boundary_job = job_kernel.CreateJobObjectW(None, None)
            if not boundary_job:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = job.ExtendedLimits()
            if action in JOB_PROBE_ACTIONS:
                slot = job.select_mapping(*job.read_windows_topology())["workers"][0]
                limits.basic.flags = 0x0008 | 0x0010 | 0x2000
                limits.basic.active_limit = 1
                limits.basic.affinity = 1 << slot["logical_processor"]
                result.update({"slot": slot["slot"], "logical_processor": slot["logical_processor"],
                               "expected_affinity": limits.basic.affinity})
            else:
                limits.basic.flags = 0x0008 | 0x0100 | 0x0200 | 0x2000
                limits.basic.active_limit = 1 if action in {"owned_python_direct", "owned_python_direct_recheck",
                                                           "owned_python_direct_recheck2"} else 2
                limits.process_memory = limits.job_memory = job.MEMORY_LIMIT
            if not job_kernel.SetInformationJobObject(boundary_job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not job_kernel.AssignProcessToJobObject(boundary_job, process.process):
                raise ctypes.WinError(ctypes.get_last_error())
            if action in JOB_PROBE_ACTIONS:
                observed = job.ExtendedLimits()
                if not job_kernel.QueryInformationJobObject(boundary_job, 9, ctypes.byref(observed),
                                                             ctypes.sizeof(observed), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                result["job_limits"] = {"flags": observed.basic.flags,
                                        "active_processes": observed.basic.active_limit,
                                        "affinity": observed.basic.affinity,
                                        "process_memory": observed.process_memory,
                                        "job_memory": observed.job_memory}
                if (observed.basic.flags & (0x0008 | 0x0010 | 0x2000) != (0x0008 | 0x0010 | 0x2000)
                        or observed.basic.flags & (0x0100 | 0x0200 | 0x0800 | 0x1000)
                        or observed.basic.active_limit != 1
                        or observed.basic.affinity != result["expected_affinity"]):
                    raise OSError("组合探针作业限制与新合同不一致。")
        result["stage"] = "inspect_token"
        if not advapi.OpenProcessToken(process.process, 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        length = wintypes.DWORD()
        is_container, is_lpac = wintypes.DWORD(), wintypes.DWORD()
        elevation_type, elevation = wintypes.DWORD(), wintypes.DWORD()
        for kind, target in ((18, elevation_type), (20, elevation)):
            if not advapi.GetTokenInformation(token, kind, ctypes.byref(target), ctypes.sizeof(target),
                                               ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
        result.update({"target_elevation_type": elevation_type.value, "target_elevation": elevation.value})
        if not advapi.GetTokenInformation(token, 29, ctypes.byref(is_container), ctypes.sizeof(is_container),
                                           ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        observed_lpac = None
        if not control:
            ctypes.set_last_error(0)
            if advapi.GetTokenInformation(token, 46, ctypes.byref(is_lpac), ctypes.sizeof(is_lpac),
                                           ctypes.byref(length)):
                observed_lpac = bool(is_lpac.value)
            else:
                error = ctypes.get_last_error()
                result["lpac_query_error"] = error
                if error != 87:
                    raise ctypes.WinError(error)
        result.update({"is_appcontainer": bool(is_container.value), "is_lpac": observed_lpac,
                       "lpac_state_verified": observed_lpac is not None})
        if not control:
            advapi.GetTokenInformation(token, 31, None, 0, ctypes.byref(length))
            if not ctypes.sizeof(ctypes.c_void_p) <= length.value <= 65536:
                raise OSError("AppContainer SID 信息长度无效。")
            token_sid_info = ctypes.create_string_buffer(length.value)
            if not advapi.GetTokenInformation(token, 31, token_sid_info, length.value, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            token_sid = ctypes.cast(token_sid_info, ctypes.POINTER(ctypes.c_void_p)).contents.value
            advapi.GetTokenInformation(token, 30, None, 0, ctypes.byref(length))
            if not 4 <= length.value <= 65536:
                raise OSError("AppContainer capability 信息长度无效。")
            capabilities = ctypes.create_string_buffer(length.value)
            if not advapi.GetTokenInformation(token, 30, capabilities, length.value, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            result.update({"sid_matches": bool(advapi.EqualSid(sid, token_sid)),
                           "capability_count": ctypes.cast(capabilities, ctypes.POINTER(wintypes.DWORD)).contents.value})
            if not result["is_appcontainer"] or not result["sid_matches"] or result["capability_count"] != 0:
                raise OSError("挂起进程的AppContainer身份或capability不符合要求。")
        result["stage"] = "resume_and_wait"
        result["resume_status"] = ntdll.NtResumeProcess(process.process)
        if result["resume_status"] != 0:
            raise OSError("无法恢复自建身份探针。")
        if action == "owned_python_job_timeout":
            remaining = max(0.0, 15.0 - (time.monotonic() - started))
            wait_ms = int(remaining * 1000 + 0.999)
        else:
            wait_ms = 5000
        wait = kernel.WaitForSingleObject(process.process, wait_ms)
        result["wait_status"] = wait
        if action == "owned_python_job_timeout" and wait == 258:
            result["elapsed_before_termination"] = time.monotonic() - started
            if not job_kernel.TerminateJobObject(boundary_job, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            result["termination_wait_status"] = kernel.WaitForSingleObject(process.process, 5000)
            if result["termination_wait_status"] != 0:
                raise OSError("超时探针未终止。")
        elif wait != 0:
            raise OSError("自建身份探针未按时结束。")
        elif action == "owned_python_job_timeout":
            raise OSError("超时探针意外提前退出。")
        completed = True
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.process, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        result["exit_code"] = exit_code.value
        if diagnostic_path is not None:
            output_sink.close()
            result["diagnostic_path"] = str(diagnostic_path)
            result["diagnostic_size_bytes"] = diagnostic_path.stat().st_size
            with diagnostic_path.open("rb") as diagnostic:
                result["diagnostic_output"] = diagnostic.read(4096).decode("mbcs", errors="replace")
        if stderr_sink is not None:
            stderr_sink.close()
            result["stderr_path"] = str(stderr_path)
            result["stderr_size_bytes"] = stderr_path.stat().st_size
            with stderr_path.open("rb") as diagnostic:
                result["stderr_output"] = diagnostic.read(4096).decode("mbcs", errors="replace")
        result["stage"] = "completed"
        if control:
            result["passed"] = not result["is_appcontainer"] and exit_code.value == 0
        else:
            result["identity_verified"] = (result["is_appcontainer"] and result["sid_matches"]
                                           and result["capability_count"] == 0)
            result["identity_passed"] = (result["identity_verified"] and
                                         (exit_code.value == 0 or
                                          (action == "owned_python_job_timeout" and wait == 258
                                           and result.get("termination_wait_status") == 0)))
            result["passed"] = result["identity_passed"] and _lpac_mode_acceptable(lpac, observed_lpac)
            if action in {"owned_python_direct", "owned_python_direct_recheck", "owned_python_direct_recheck2"}:
                result["runtime_evidence"] = _runtime_evidence(result.get("diagnostic_output", ""), reused_profile)
                result["passed"] = result["passed"] and result["runtime_evidence"]["passed"]
            elif action == "owned_python_job":
                result["combined_evidence"] = _combined_evidence(result.get("diagnostic_output", ""),
                                                                  process.pid, result["expected_affinity"])
                result["passed"] = result["passed"] and result["combined_evidence"]["passed"]
            elif action == "owned_python_job_timeout":
                result["passed"] = (result["identity_passed"] and _lpac_mode_acceptable(lpac, observed_lpac)
                                    and result["wait_status"] == 258 and result["termination_wait_status"] == 0
                                    and result["exit_code"] != 0 and result["elapsed_before_termination"] >= 15)
    except OSError as exc:
        result["error"] = str(exc)
        result["winerror"] = getattr(exc, "winerror", None)
    finally:
        if boundary_job:
            job_kernel.CloseHandle(boundary_job)  # 仅终止本探针作业的剩余进程。
        if process.process and not completed:
            kernel.TerminateProcess(process.process, 1)
            kernel.WaitForSingleObject(process.process, 5000)
        if token:
            kernel.CloseHandle(token)
        if process.thread:
            kernel.CloseHandle(process.thread)
        if process.process:
            kernel.CloseHandle(process.process)
        if attributes_initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        if sid:
            advapi.FreeSid(sid)
        if output_sink is not None:
            output_sink.close()
        if stderr_sink is not None:
            stderr_sink.close()
        if input_sink is not None:
            input_sink.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 AppContainer 身份；显式创建的配置保留，不自动删除。")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--lpac", action="store_true", help="同时请求限制 ALL APPLICATION PACKAGES 的 LPAC")
    mode.add_argument("--control", action="store_true", help="不启用 AppContainer，验证相同进程启动路径")
    mode.add_argument("--create-profile", metavar="NAME", help="需授权；新建 P0Task3Probe_YYYYMMDD_NN 配置")
    mode.add_argument("--retry-profile-from", metavar="RECORD", help="仅重试先前创建记录中的配置")
    parser.add_argument("--record", help="在 outputs 新建 p0_task3_appcontainer_*.jsonl，不得覆盖")
    options = parser.parse_args()
    if options.create_profile and not re.fullmatch(r"P0Task3Probe_[0-9]{8}_[0-9]{2}", options.create_profile):
        parser.error("配置名称须符合 P0Task3Probe_YYYYMMDD_NN。")
    if options.record and not re.fullmatch(r"p0_task3_appcontainer_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名须为 p0_task3_appcontainer_*.jsonl，且不能包含路径。")
    if options.retry_profile_from and not re.fullmatch(r"p0_task3_appcontainer_[a-z0-9_]+\.jsonl",
                                                       options.retry_profile_from):
        parser.error("身份来源须是 outputs 下的任务3记录文件名。")
    if (options.create_profile or options.retry_profile_from) and not options.record:
        parser.error("创建或重试配置时必须提供新建记录文件。")

    def execute(stream=None):
        def save(event):
            if stream is not None:
                stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
                stream.flush()
        save({"event": "source", "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        try:
            if options.retry_profile_from:
                original = _recorded_profile(options.retry_profile_from)
                save({"event": "source_profile_record", "record": original["source_record"],
                      "sha256": original["source_record_sha256"]})
                result = run_probe(sink=save, reused_profile=original)
            else:
                result = run_probe(options.lpac, options.control, options.create_profile, save)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
        return result

    if options.record:
        with (Path(__file__).resolve().parents[1] / "outputs" / options.record).open(
                "x", encoding="utf-8", newline="\n") as record:
            result = execute(record)
    else:
        result = execute()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
