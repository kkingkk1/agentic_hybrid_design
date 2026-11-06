"""核验受限进程的真实管道与监督；只允许运行固定的无害探针。"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import ctypes
from ctypes import wintypes
import hashlib
import ipaddress
import json
import msvcrt
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
    from . import p0_sandbox_runtime as runtime
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job
    import p0_sandbox_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
BUILD_CODE = "import sys; p=sys.argv[1]; compile(open(p,'rb').read(),p,'exec',dont_inherit=True)"
OVERFLOW_CODE = "import sys,time; sys.stdout.buffer.write(b'x'*20000); sys.stdout.flush(); time.sleep(30)"
ERR_OVERFLOW_CODE = "import sys,time; sys.stderr.buffer.write(b'x'*70000); sys.stderr.flush(); time.sleep(30)"
TIMEOUT_CODE = "import time; time.sleep(30)"
HOLD_CODE = ("import ctypes,json,os,time; from ctypes import wintypes; "
             "k=ctypes.WinDLL('kernel32',use_last_error=True); k.GetCurrentProcess.restype=wintypes.HANDLE; "
             "k.GetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),"
             "ctypes.POINTER(ctypes.c_size_t)]; k.GetProcessAffinityMask.restype=wintypes.BOOL; "
             "p=ctypes.c_size_t(); s=ctypes.c_size_t(); "
             "assert k.GetProcessAffinityMask(k.GetCurrentProcess(),ctypes.byref(p),ctypes.byref(s)); "
             "print(json.dumps({'pid':os.getpid(),'affinity':p.value}),flush=True); time.sleep(5)")
READ_CODE = ("import json,sys\n"
             "try:\n with open(sys.argv[1],'rb') as f: f.read(1)\n"
             "except PermissionError:\n print(json.dumps({'result':'denied'}))\n"
             "else:\n print(json.dumps({'result':'read'}))\n")
NETWORK_CODE = ("import json,socket,sys\n"
                "try:\n s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=3)\n"
                "except OSError as e:\n print(json.dumps({'connected':False,'error':e.errno}))\n"
                "else:\n s.close(); print(json.dumps({'connected':True}))\n")
PROBE_MODES = {"build_valid", "build_invalid", "json", "stdout_limit", "stderr_limit", "timeout", "hold",
               "read_own", "read_other", "read_own_runtime", "read_other_runtime", "read_host",
               "loopback", "local_network"}


def _local_private_ipv4() -> list[str]:
    private = tuple(ipaddress.ip_network(item) for item in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    addresses = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None,
                                                           socket.AF_INET, socket.SOCK_STREAM)}
    return sorted(address for address in addresses if any(ipaddress.ip_address(address) in network
                                                           for network in private))


def _verified_profiles() -> list[dict]:
    manifest = json.loads(runtime.MANIFEST.read_bytes())
    profiles = []
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("缺少 LOCALAPPDATA。")
    for name, record in identity.PROFILE_RECORDS.items():
        profile = identity._recorded_profile(record)
        expected = Path(local) / "Packages" / name.lower() / "AC"
        actual = Path(profile["profile_folder"])
        if profile["profile_name"] != name or os.path.normcase(os.path.normpath(actual)) != os.path.normcase(os.path.normpath(expected)):
            raise ValueError("测试身份目录与记录不一致。")
        for path in (actual.parent.parent, actual.parent, actual):
            runtime._safe_stat(path)
        destination = actual / identity.RUNTIME_DIR
        count = runtime._verify_copied(destination, manifest)
        if count != manifest["file_count"]:
            raise ValueError("运行时清单不完整。")
        profiles.append(profile)
    if len(profiles) != 2 or profiles[0]["profile_sid"] == profiles[1]["profile_sid"]:
        raise ValueError("测试身份不独立。")
    return profiles


def _probe_args(profile: dict, other: dict, mode: str, port: int | None = None,
                network_address: str | None = None) -> list[str]:
    if mode not in PROBE_MODES:
        raise ValueError("只允许固定的无害探针，不接受候选程序。")
    base = Path(profile["profile_folder"])
    python = base / identity.RUNTIME_DIR / "python.exe"
    tool = base / identity.RUNTIME_DIR / "Lib" / "json" / "tool.py"
    own = base / identity.OWN_FIXTURE_NAME
    other_file = Path(other["profile_folder"]) / identity.OWN_FIXTURE_NAME
    if mode == "build_valid":
        return [str(python), "-I", "-B", "-c", BUILD_CODE, str(tool)]
    if mode == "build_invalid":
        return [str(python), "-I", "-B", "-c", BUILD_CODE, str(own)]
    if mode == "json":
        return [str(python), "-I", "-B", str(tool)]
    if mode in {"stdout_limit", "stderr_limit", "timeout", "hold"}:
        code = {"stdout_limit": OVERFLOW_CODE, "stderr_limit": ERR_OVERFLOW_CODE,
                "timeout": TIMEOUT_CODE, "hold": HOLD_CODE}[mode]
        return [str(python), "-I", "-B", "-c", code]
    if mode in {"read_own", "read_other", "read_own_runtime", "read_other_runtime", "read_host"}:
        target = {"read_own": own, "read_other": other_file, "read_own_runtime": tool,
                  "read_other_runtime": Path(other["profile_folder"]) / identity.RUNTIME_DIR / "Lib" / "json" / "tool.py",
                  "read_host": identity.BOUNDARY_FIXTURE}[mode]
        return [str(python), "-I", "-B", "-c", READ_CODE, str(target)]
    if type(port) is not int or not 0 < port <= 65535:
        raise ValueError("网络探针端口无效。")
    if mode == "loopback":
        address = "127.0.0.1"
        if network_address not in (None, address):
            raise ValueError("回环探针地址无效。")
    elif mode == "local_network" and network_address in _local_private_ipv4():
        address = network_address
    else:
        raise ValueError("只允许本机回环和本机局域网地址。")
    return [str(python), "-I", "-B", "-c", NETWORK_CODE, address, str(port)]


def _windows_api():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("受限探针仅支持已核验的64位Windows。")
    kernel, ntdll = job._apis()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.FreeSid.argtypes = [ctypes.c_void_p]
    advapi.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    advapi.EqualSid.restype = wintypes.BOOL
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                                          ctypes.POINTER(ctypes.c_size_t)]
    kernel.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                                  ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    kernel.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel.CreateProcessW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p,
                                     wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, ctypes.c_wchar_p,
                                     ctypes.POINTER(identity.StartupInfoEx), ctypes.POINTER(identity.ProcessInfo)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    return kernel, ntdll, advapi, userenv


def _token_evidence(kernel, advapi, process, sid) -> dict:
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(process, 0x0008, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        values = {}
        for number, key in ((20, "elevated"), (29, "appcontainer")):
            value = wintypes.DWORD()
            if not advapi.GetTokenInformation(token, number, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            values[key] = value.value
        buffers = {}
        for number in (30, 31):
            advapi.GetTokenInformation(token, number, None, 0, ctypes.byref(size))
            if not ctypes.sizeof(ctypes.c_void_p) <= size.value <= 65536:
                raise OSError("身份令牌信息长度无效。")
            buffers[number] = ctypes.create_string_buffer(size.value)
            if not advapi.GetTokenInformation(token, number, buffers[number], size.value, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
        target_sid = ctypes.cast(buffers[31], ctypes.POINTER(ctypes.c_void_p)).contents.value
        values["sid_matches"] = bool(advapi.EqualSid(sid, target_sid))
        values["capabilities"] = ctypes.cast(buffers[30], ctypes.POINTER(wintypes.DWORD)).contents.value
        if values != {"elevated": 0, "appcontainer": 1, "sid_matches": True, "capabilities": 0}:
            raise OSError("受限进程的身份或权限不符合要求。")
        return values
    finally:
        kernel.CloseHandle(token)


class _PipeReader:
    def __init__(self, fd: int, limit: int):
        self.fd, self.limit = fd, limit
        self.data = bytearray()
        self.observed = 0
        self.exceeded = threading.Event()
        self.error = None
        self.finished_monotonic = None
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self):
        try:
            while True:
                data = os.read(self.fd, 4096)
                if not data:
                    break
                self.observed += len(data)
                self.data.extend(data[:max(0, self.limit - len(self.data))])
                if self.observed > self.limit:
                    self.exceeded.set()
                    break
        except OSError as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.finished_monotonic = time.monotonic()
            os.close(self.fd)


def _write_input(fd: int, data: bytes, result: dict):
    try:
        sent = 0
        while sent < len(data):
            written = os.write(fd, data[sent:])
            if written <= 0:
                raise OSError("输入管道未写入数据。")
            sent += written
        result["sent"] = sent
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        os.close(fd)


def _run_fixed(profile: dict, other: dict, slot: dict, mode: str, payload: bytes = b"",
               port: int | None = None, network_address: str | None = None) -> dict:
    """运行白名单探针；没有候选源码、任意文件或任意命令入口。"""
    if type(payload) is not bytes or len(payload) > 65536:
        raise ValueError("探针输入无效。")
    for candidate in (profile, other):
        name = candidate.get("profile_name") if type(candidate) is dict else None
        if name not in identity.PROFILE_RECORDS:
            raise ValueError("只允许已授权的测试身份。")
        original = identity._recorded_profile(identity.PROFILE_RECORDS[name])
        if (candidate.get("profile_sid") != original["profile_sid"]
                or os.path.normcase(os.path.normpath(candidate.get("profile_folder", "")))
                != os.path.normcase(os.path.normpath(original["profile_folder"]))):
            raise ValueError("测试身份与记录不一致。")
    if profile["profile_sid"] == other["profile_sid"]:
        raise ValueError("测试身份不独立。")
    arguments = _probe_args(profile, other, mode, port, network_address)
    logical = slot["logical_processor"]
    if type(logical) is not int or not 0 <= logical < 64:
        raise ValueError("逻辑处理器无效。")
    resources = job._resource_gate()
    kernel, ntdll, advapi, userenv = _windows_api()
    sid, sid_string = ctypes.c_void_p(), ctypes.c_wchar_p()
    process = identity.ProcessInfo()
    job_handle = None
    attributes = None
    initialized = False
    fds = set()
    readers = []
    started_readers = []
    writer = None
    writer_started = False
    assigned = False
    finished = False
    input_result = {}
    try:
        status = userenv.DeriveAppContainerSidFromAppContainerName(profile["profile_name"], ctypes.byref(sid))
        if status != 0 or not sid:
            raise OSError("无法派生已授权身份。")
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
            raise ctypes.WinError(ctypes.get_last_error())
        if sid_string.value != profile["profile_sid"]:
            raise OSError("派生身份与创建记录不一致。")

        in_read, in_write = os.pipe()
        fds.update((in_read, in_write))
        out_read, out_write = os.pipe()
        fds.update((out_read, out_write))
        err_read, err_write = os.pipe()
        fds.update((err_read, err_write))
        child_fds = (in_read, out_write, err_write)
        handles = [msvcrt.get_osfhandle(fd) for fd in child_fds]
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        inherited = (wintypes.HANDLE * 3)(*handles)
        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        initialized = True
        caps = identity.SecurityCapabilities(sid, None, 0, 0)
        if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020009, ctypes.byref(caps),
                                                ctypes.sizeof(caps), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020002, ctypes.byref(inherited),
                                                ctypes.sizeof(inherited), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = identity.StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.startup.flags = 0x00000100
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
        root = os.environ.get("SystemRoot", r"C:\Windows")
        environment = ctypes.create_unicode_buffer(identity._child_environment(root))
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        flags = 0x00080000 | 0x00000004 | 0x08000000 | 0x00000400 | subprocess.NORMAL_PRIORITY_CLASS
        start = time.monotonic()
        if not kernel.CreateProcessW(arguments[0], command, None, None, True, flags, environment,
                                     profile["profile_folder"], ctypes.byref(startup), ctypes.byref(process)):
            raise ctypes.WinError(ctypes.get_last_error())
        for fd in child_fds:
            os.close(fd)
            fds.remove(fd)

        job_handle = kernel.CreateJobObjectW(None, None)
        if not job_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = job.ExtendedLimits()
        limits.basic.flags = 0x0008 | 0x0010 | 0x2000
        limits.basic.active_limit = 1
        limits.basic.affinity = 1 << logical
        if not kernel.SetInformationJobObject(job_handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job_handle, process.process):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned = True
        observed = job.ExtendedLimits()
        if not kernel.QueryInformationJobObject(job_handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if (observed.basic.flags & (0x0008 | 0x0010 | 0x2000) != (0x0008 | 0x0010 | 0x2000)
                or observed.basic.flags & (0x0001 | 0x0100 | 0x0200 | 0x0800 | 0x1000)
                or observed.basic.active_limit != 1 or observed.basic.affinity != 1 << logical):
            raise OSError("受限作业的进程、绑定或内存配置不符合合同。")
        evidence = _token_evidence(kernel, advapi, process.process, sid)
        deadline = start + (30 if mode.startswith("build_") else 15)
        if time.monotonic() >= deadline:
            raise TimeoutError("受限进程启动已超过时限，不恢复执行。")
        readers = [_PipeReader(out_read, job.STDOUT_LIMIT), _PipeReader(err_read, job.STDERR_LIMIT)]
        for reader in readers:
            reader.thread.start()
            started_readers.append(reader)
            fds.remove(reader.fd)
        if ntdll.NtResumeProcess(process.process) != 0:
            raise OSError("无法恢复挂起的探针进程。")
        resumed = time.monotonic()
        writer = threading.Thread(target=_write_input, args=(in_write, payload, input_result), daemon=True)
        writer.start()
        writer_started = True
        fds.remove(in_write)
        reason = "exited"
        while True:
            wait = kernel.WaitForSingleObject(process.process, 0)
            now = time.monotonic()
            if readers[0].exceeded.is_set() or readers[1].exceeded.is_set():
                reason = "stdout_limit" if readers[0].exceeded.is_set() else "stderr_limit"
                break
            if now >= deadline:
                reason = "timeout"
                break
            if wait == 0:
                break
            if wait != 258:
                raise OSError(f"等待受限进程失败：{wait}")
            time.sleep(0.01)
        if reason != "exited" and wait != 0:
            if not kernel.TerminateJobObject(job_handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
        if kernel.WaitForSingleObject(process.process, 5000) != 0:
            raise OSError("受限进程未能结束。")
        finished = True
        ended = time.monotonic()
        writer.join(timeout=5)
        for reader in readers:
            reader.thread.join(timeout=5)
        if writer.is_alive() or any(reader.thread.is_alive() or reader.error for reader in readers):
            raise OSError("输入或输出管道未正确结束。")
        completed = max(ended, *(reader.finished_monotonic for reader in readers))
        if readers[0].exceeded.is_set():
            reason = "stdout_limit"
        elif readers[1].exceeded.is_set():
            reason = "stderr_limit"
        elif reason == "exited" and (input_result.get("error") or input_result.get("sent") != len(payload)):
            reason = "input_error"
        elif reason == "exited" and completed > deadline:
            reason = "timeout"
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.process, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        accounting = job.Accounting()
        if not kernel.QueryInformationJobObject(job_handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"mode": mode, "pid": process.pid, "slot": slot["slot"], "logical_processor": logical,
                "identity": evidence, "job_flags": observed.basic.flags, "affinity": observed.basic.affinity,
                "resource_precheck": resources,
                "reason": reason, "exit_code": exit_code.value, "elapsed_seconds": completed - start,
                "resumed_monotonic": resumed, "finished_monotonic": completed,
                "cpu_seconds": (accounting.user + accounting.kernel) / 10_000_000,
                "stdout_bytes": readers[0].observed, "stderr_bytes": readers[1].observed,
                "stdout_b64": base64.b64encode(readers[0].data).decode("ascii"),
                "stderr_b64": base64.b64encode(readers[1].data).decode("ascii"), "input": input_result}
    finally:
        if process.process and not finished:
            if assigned and job_handle:
                kernel.TerminateJobObject(job_handle, 1)
            else:
                kernel.TerminateProcess(process.process, 1)
            kernel.WaitForSingleObject(process.process, 5000)
        if writer_started:
            writer.join(timeout=5)
        for reader in started_readers:
            reader.thread.join(timeout=5)
        for fd in fds:
            os.close(fd)
        if job_handle:
            kernel.CloseHandle(job_handle)
        if process.thread:
            kernel.CloseHandle(process.thread)
        if process.process:
            kernel.CloseHandle(process.process)
        if initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        if sid_string:
            kernel.LocalFree(ctypes.cast(sid_string, ctypes.c_void_p))
        if sid:
            advapi.FreeSid(sid)


def _stdout(result: dict) -> bytes:
    return base64.b64decode(result["stdout_b64"], validate=True)


def _basic_checks(results: dict, payload: dict) -> bool:
    try:
        valid, invalid, echo, overflow, err_overflow = (results[key] for key in
                                                       ("build_valid", "build_invalid", "json", "stdout_limit",
                                                        "stderr_limit"))
        return (valid["reason"] == "exited" and valid["exit_code"] == 0
                and invalid["reason"] == "exited" and invalid["exit_code"] != 0
                and echo["reason"] == "exited" and echo["exit_code"] == 0
                and json.loads(_stdout(echo)) == payload
                and overflow["reason"] == "stdout_limit" and overflow["stdout_bytes"] > job.STDOUT_LIMIT
                and len(_stdout(overflow)) <= job.STDOUT_LIMIT
                and err_overflow["reason"] == "stderr_limit" and err_overflow["stderr_bytes"] > job.STDERR_LIMIT
                and len(base64.b64decode(err_overflow["stderr_b64"], validate=True)) <= job.STDERR_LIMIT)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _read_result(result: dict, expected: str) -> bool:
    try:
        return (result["reason"] == "exited" and result["exit_code"] == 0
                and json.loads(_stdout(result)) == {"result": expected})
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _network_check(profiles: list[dict], slot: dict, save, address: str) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((address, 0))
        listener.listen(4)
        listener.settimeout(0.2)
        port = listener.getsockname()[1]
        requests, errors = [], []
        stop = threading.Event()

        def serve():
            while not stop.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not stop.is_set():
                        errors.append(type(exc).__name__)
                    return
                with connection:
                    requests.append(True)

        server = threading.Thread(target=serve, name="p0-restricted-loopback", daemon=True)
        server.start()
        try:
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(requests) < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            before = len(requests)
            mode = "loopback" if address == "127.0.0.1" else "local_network"
            probe = _run_fixed(profiles[0], profiles[1], slot, mode, port=port, network_address=address)
            save({"event": "probe", "profile": 0, "result": probe})
            time.sleep(0.25)
            after = len(requests)
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(requests) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            final = len(requests)
        finally:
            stop.set()
            server.join(timeout=3)
            if server.is_alive():
                errors.append("server_not_stopped")
    try:
        network = (probe["reason"] == "exited" and probe["exit_code"] == 0
                   and json.loads(_stdout(probe)).get("connected") is False
                   and (before, after, final) == (1, 1, 2) and not errors)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        network = False
    return {"address": address, "blocked": network, "host_connection_counts": [before, after, final],
            "server_errors": errors}


def _run_boundary(profiles: list[dict], slot: dict, save) -> dict:
    expected_text = "P0 simulated sensitive data; not a real secret.\n"
    paths = [Path(profile["profile_folder"]) / identity.OWN_FIXTURE_NAME for profile in profiles]
    paths.append(identity.BOUNDARY_FIXTURE)
    if any(path.read_text(encoding="utf-8") != expected_text for path in paths):
        raise OSError("宿主无法核对模拟文件，不能判定隔离。")
    checks = []
    for index in (0, 1):
        for mode, expected in (("read_own", "read"), ("read_other", "denied"), ("read_host", "denied")):
            result = _run_fixed(profiles[index], profiles[1 - index], slot, mode)
            save({"event": "probe", "profile": index, "result": result})
            checks.append(_read_result(result, expected))
    addresses = _local_private_ipv4()
    if not addresses:
        raise OSError("没有可核验的本机局域网地址。")
    networks = [_network_check(profiles, slot, save, "127.0.0.1"),
                _network_check(profiles, slot, save, addresses[0])]
    return {"passed": all(checks) and all(item["blocked"] for item in networks),
            "file_checks": checks, "network_checks": networks}


def _run_parallel(profiles: list[dict], slots: list[dict], save) -> dict:
    def run_one(slot):
        index = slot["slot"] % 2
        return _run_fixed(profiles[index], profiles[1 - index], slot, "hold")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(run_one, slots))
    for result in results:
        save({"event": "probe", "result": result})
    try:
        valid = all(item["reason"] == "exited" and item["exit_code"] == 0
                    and json.loads(_stdout(item)) == {"pid": item["pid"], "affinity": 1 << item["logical_processor"]}
                    for item in results)
        overlap = max(item["resumed_monotonic"] for item in results) < min(item["finished_monotonic"] for item in results)
        passed = valid and overlap and len(results) == 16 and len({item["logical_processor"] for item in results}) == 16
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        passed = overlap = False
    return {"passed": passed, "jobs": len(results), "simultaneous_16": overlap,
            "scope": "16个无害进程共用两个测试身份；不证明16个身份之间隔离。"}


def main() -> int:
    parser = argparse.ArgumentParser(description="只运行固定的无害受限进程探针。")
    parser.add_argument("--record", required=True, help="在 outputs 新建 p0_task3_restricted_*.jsonl")
    parser.add_argument("--case", choices=("basic", "boundary", "runtime_boundary", "parallel", "timeout"),
                        default="basic")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_restricted_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名须为 p0_task3_restricted_*.jsonl，不得包含路径。")
    with (ROOT / "outputs" / options.record).open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        source_paths = [Path(__file__), ROOT / "scripts" / "p0_appcontainer_probe.py",
                        ROOT / "scripts" / "p0_job_probe.py", ROOT / "scripts" / "p0_sandbox_runtime.py"]
        save({"event": "sources", "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                                for path in source_paths}})
        result = {"passed": False, "scope": "仅固定无害探针，不运行候选。"}
        try:
            result["resource_precheck"] = job._resource_gate()
            profiles = _verified_profiles()
            slots = job.select_mapping(*job.read_windows_topology())["workers"]
            if options.case == "basic":
                payload = {"probe": "stdin", "values": [1, 2, 3]}
                results = {}
                for mode in ("build_valid", "build_invalid", "json", "stdout_limit", "stderr_limit"):
                    raw = json.dumps(payload).encode("utf-8") if mode == "json" else b""
                    results[mode] = _run_fixed(profiles[0], profiles[1], slots[0], mode, raw)
                    save({"event": "probe", "result": results[mode]})
                result.update({"checks": results, "passed": _basic_checks(results, payload)})
            elif options.case == "boundary":
                result.update(_run_boundary(profiles, slots[0], save))
            elif options.case == "runtime_boundary":
                checks = []
                for index in (0, 1):
                    for mode, expected in (("read_own_runtime", "read"), ("read_other_runtime", "denied")):
                        probe = _run_fixed(profiles[index], profiles[1 - index], slots[index], mode)
                        save({"event": "probe", "profile": index, "result": probe})
                        checks.append(_read_result(probe, expected))
                result.update({"passed": all(checks), "file_checks": checks,
                               "scope": "只检查两个测试身份对各自和对方运行时文件的读取。"})
            elif options.case == "parallel":
                result.update(_run_parallel(profiles, slots, save))
            else:
                timeout_result = _run_fixed(profiles[0], profiles[1], slots[0], "timeout")
                save({"event": "probe", "result": timeout_result})
                result["passed"] = (timeout_result["reason"] == "timeout" and timeout_result["exit_code"] != 0
                                    and timeout_result["elapsed_seconds"] >= 15)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        save({"event": "result", "result": result})
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
