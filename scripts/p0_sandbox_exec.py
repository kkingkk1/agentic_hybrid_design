"""P0 的受限构建和求解入口；只有无害入口探针通过后才允许执行候选。"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import ctypes
from ctypes import wintypes
import hashlib
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
    from . import p0_restricted_probe as probe
    from . import p0_sandbox_runtime as runtime
    from . import p0_slot_setup as setup
    from . import p0_slot_verify as slots
    from . import p0_tsp_evaluator as evaluator
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job
    import p0_restricted_probe as probe
    import p0_sandbox_runtime as runtime
    import p0_slot_setup as setup
    import p0_slot_verify as slots
    import p0_tsp_evaluator as evaluator


ROOT = Path(__file__).resolve().parents[1]
SLOT_RECORD = ROOT / "outputs" / "p0_task3_slots_verify_20261105_01.jsonl"
MAX_SOURCE_BYTES = 1024 * 1024
CHILD_PROBE = '''
import json, subprocess, sys
results = []
for flags in (0, 0x01000000):
    try:
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", "pass"], creationflags=flags)
    except OSError as exc:
        results.append({"created": False, "winerror": getattr(exc, "winerror", None)})
    else:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        results.append({"created": True})
print(json.dumps(results))
'''
AFFINITY_PROBE = '''
import ctypes, json, sys
from ctypes import wintypes
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.GetCurrentProcess.restype = wintypes.HANDLE
k.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
k.GetProcessAffinityMask.restype = wintypes.BOOL
k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
k.SetProcessAffinityMask.restype = wintypes.BOOL
p = k.GetCurrentProcess()
before, system = ctypes.c_size_t(), ctypes.c_size_t()
if not k.GetProcessAffinityMask(p, ctypes.byref(before), ctypes.byref(system)):
    raise ctypes.WinError(ctypes.get_last_error())
ctypes.set_last_error(0)
changed = bool(k.SetProcessAffinityMask(p, int(sys.argv[1])))
error = 0 if changed else ctypes.get_last_error()
after = ctypes.c_size_t()
if not k.GetProcessAffinityMask(p, ctypes.byref(after), ctypes.byref(system)):
    raise ctypes.WinError(ctypes.get_last_error())
print(json.dumps({"before": before.value, "after": after.value, "changed": changed, "error": error}))
'''
TSP_PROBE = ("import json,sys; data=json.load(sys.stdin); "
             "print(json.dumps({'tour':list(range(len(data['coordinates'])))}))")


def _read_events(path: Path, limit: int = 4 * 1024 * 1024) -> list[dict]:
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError("验收记录过大。")
    events = [json.loads(line) for line in raw.splitlines()]
    if not events or any(type(event) is not dict for event in events):
        raise ValueError("验收记录格式错误。")
    return events


def _slot_evidence() -> dict:
    plan = json.loads(setup.PLAN.read_text(encoding="utf-8"))
    if plan != setup.build_plan():
        raise ValueError("已批准的身份准备清单或来源代码已改变。")
    events = _read_events(SLOT_RECORD)
    sources = events[0].get("sha256", {})
    if (events[0].get("event") != "sources" or events[-1].get("event") != "result"
            or events[-1].get("result", {}).get("passed") is not True
            or sources != plan["program_sources_sha256"]):
        raise ValueError("16身份隔离验收记录不完整或来源不一致。")
    return plan


def _require_probe_gate() -> dict:
    plan = _slot_evidence()
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    slot_hash = hashlib.sha256(SLOT_RECORD.read_bytes()).hexdigest()
    for path in sorted((ROOT / "outputs").glob("p0_task3_executor_probe_*.jsonl")):
        try:
            events = _read_events(path)
            if (events[0].get("event") == "sources" and events[0].get("executor_sha256") == source_hash
                    and events[0].get("slot_record_sha256") == slot_hash
                    and events[-1].get("event") == "result" and events[-1].get("result", {}).get("passed") is True):
                return plan
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    raise OSError("实际构建与求解入口尚未通过无害探针，禁止执行候选。")


def _require_gate() -> dict:
    plan = _require_probe_gate()
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fixture_hash = hashlib.sha256((ROOT / "scripts" / "p0_sandbox_fixture_probe.py").read_bytes()).hexdigest()
    for path in sorted((ROOT / "outputs").glob("p0_task3_fixture_file_interface_*.jsonl")):
        try:
            events = _read_events(path)
            result = events[-1].get("result", {})
            if (events[0].get("event") == "sources" and events[0].get("executor_sha256") == source_hash
                    and events[0].get("probe_sha256") == fixture_hash
                    and events[-1].get("event") == "result" and result.get("passed") is True
                    and result.get("evaluation") == {"valid": True, "objective": 4.0}):
                return plan
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    raise OSError("当前入口尚未通过无害源码文件探针，禁止执行候选。")


def _profile(plan: dict, name: str) -> dict:
    matches = [target for target in plan["targets"] if target["name"] == name]
    if len(matches) != 1:
        raise ValueError("身份不属于已批准的P0清单。")
    target = matches[0]
    record = Path(target["profile_record"])
    setup._check_plan_provenance(record, hashlib.sha256(setup.PLAN.read_bytes()).hexdigest())
    profile = identity._recorded_profile(record.name)
    if (profile["profile_name"] != name or os.path.normcase(os.path.normpath(profile["profile_folder"]))
            != os.path.normcase(os.path.normpath(target["profile_dir"]))):
        raise ValueError("身份目录与记录不一致。")
    folder = Path(profile["profile_folder"])
    for path in (folder.parent.parent, folder.parent, folder):
        runtime._safe_stat(path)
    manifest, _ = setup._manifest()
    runtime._verify_copied(folder / identity.RUNTIME_DIR, manifest)
    return profile


class _LockedSource:
    """由宿主持有只读句柄，运行期间不允许写入或删除源码。"""

    def __init__(self, path: Path):
        self.path, self.kernel, self.handle = path, None, None

    def __enter__(self):
        runtime._safe_stat(self.path)
        if not self.path.is_file():
            raise ValueError("源码不是普通文件。")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateFileW(str(self.path), 0x80000000, 0x00000001, None, 3, 0x00200000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        return self

    def __exit__(self, _kind, _value, _traceback):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class _SlotGuard:
    """阻止本项目的两个受限作业同时占用同一槽位。"""

    def __init__(self, slot: int):
        self.slot, self.kernel, self.handle = slot, None, None

    def __enter__(self):
        if type(self.slot) is not int or not 0 <= self.slot < 16:
            raise ValueError("槽位无效。")
        self.kernel, _ = job._apis()
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        self.kernel.ReleaseMutex.restype = wintypes.BOOL
        self.handle = self.kernel.CreateMutexW(None, False, f"Local\\P0AgenticHybridSlot{self.slot:02d}")
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        status = self.kernel.WaitForSingleObject(self.handle, 0)
        if status not in (0, 0x80):
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            raise OSError("该槽位已有作业，不能同时分配。")
        return self

    def __exit__(self, _kind, _value, _traceback):
        if self.handle:
            self.kernel.ReleaseMutex(self.handle)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _run_program(profile: dict, slot: dict, source: Path, payload: bytes, *, build: bool,
                 probe_mode: str | None = None, other: dict | None = None,
                 port: int | None = None, network_address: str | None = None,
                 prepare_source=None, expected_source_sha: str | None = None) -> dict:
    """运行已确定的源码路径；调用方负责身份、源码和验收门禁。"""
    if type(payload) is not bytes:
        raise ValueError("标准输入须为字节。")
    if (prepare_source is None) != (expected_source_sha is None) or (prepare_source is not None and probe_mode is not None):
        raise ValueError("源码准备参数无效。")
    logical = slot["logical_processor"]
    if type(logical) is not int or not 0 <= logical < 64:
        raise ValueError("逻辑处理器无效。")
    root = Path(profile["profile_folder"])
    executable = root / identity.RUNTIME_DIR / "python.exe"
    if probe_mode is None:
        arguments = ([str(executable), "-I", "-B", "-c", probe.BUILD_CODE, str(source)] if build else
                     [str(executable), "-I", "-B", str(source)])
    else:
        allowed = {"stdout_limit", "stderr_limit", "timeout", "hold", "read_own_runtime",
                   "read_other_runtime", "read_host", "loopback", "local_network", "child_attempt",
                   "affinity_attempt", "tsp_fixture"}
        if build or probe_mode not in allowed or type(other) is not dict:
            raise ValueError("无效的固定入口探针。")
        if probe_mode in {"child_attempt", "affinity_attempt", "tsp_fixture"}:
            code = {"child_attempt": CHILD_PROBE, "affinity_attempt": AFFINITY_PROBE, "tsp_fixture": TSP_PROBE}[probe_mode]
            arguments = [str(executable), "-I", "-B", "-c", code]
            if probe_mode == "affinity_attempt":
                alternate = 17 if logical != 17 else 16
                arguments.append(str((1 << logical) | (1 << alternate)))
        else:
            arguments = probe._probe_args(profile, other, probe_mode, port, network_address)
        if os.path.normcase(os.path.normpath(arguments[0])) != os.path.normcase(os.path.normpath(str(executable))):
            raise ValueError("探针解释器与身份不一致。")
    resources = job._resource_gate()
    kernel, ntdll, advapi, userenv = probe._windows_api()
    sid, sid_string = ctypes.c_void_p(), ctypes.c_wchar_p()
    process = identity.ProcessInfo()
    job_handle, attributes = None, None
    initialized = assigned = finished = writer_started = False
    fds, readers, started_readers = set(), [], []
    writer, input_result, prepared_source = None, {}, None
    try:
        if prepare_source is not None:
            prepared_source = prepare_source()
        status = userenv.DeriveAppContainerSidFromAppContainerName(profile["profile_name"], ctypes.byref(sid))
        if status != 0 or not sid:
            raise OSError("无法派生已批准的身份。")
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
        for attribute, value, length in ((0x00020009, ctypes.byref(caps), ctypes.sizeof(caps)),
                                         (0x00020002, ctypes.byref(inherited), ctypes.sizeof(inherited))):
            if not kernel.UpdateProcThreadAttribute(attributes, 0, attribute, value, length, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        startup = identity.StartupInfoEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.startup.flags = 0x00000100
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
        environment = ctypes.create_unicode_buffer(identity._child_environment(os.environ.get("SystemRoot", r"C:\Windows")))
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        flags = 0x00080000 | 0x00000004 | 0x08000000 | 0x00000400 | subprocess.NORMAL_PRIORITY_CLASS
        start = time.monotonic()
        if not kernel.CreateProcessW(str(executable), command, None, None, True, flags, environment,
                                     str(root), ctypes.byref(startup), ctypes.byref(process)):
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
            raise OSError("受限作业配置不符合合同。")
        evidence = probe._token_evidence(kernel, advapi, process.process, sid)
        deadline = start + (30 if build else 15)
        if time.monotonic() >= deadline:
            raise TimeoutError("受限进程启动已超过时限，不恢复执行。")
        readers = [probe._PipeReader(out_read, job.STDOUT_LIMIT), probe._PipeReader(err_read, job.STDERR_LIMIT)]
        for reader in readers:
            reader.thread.start()
            started_readers.append(reader)
            fds.remove(reader.fd)
        if ntdll.NtResumeProcess(process.process) != 0:
            raise OSError("无法恢复受限进程。")
        resumed = time.monotonic()
        fds.remove(in_write)
        writer = threading.Thread(target=probe._write_input, args=(in_write, payload, input_result), daemon=True)
        try:
            writer.start()
            writer_started = True
        except BaseException:
            fds.add(in_write)
            raise
        reason = "exited"
        while True:
            wait = kernel.WaitForSingleObject(process.process, 0)
            if readers[0].exceeded.is_set() or readers[1].exceeded.is_set():
                reason = "stdout_limit" if readers[0].exceeded.is_set() else "stderr_limit"
                break
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            if wait == 0:
                break
            if wait != 258:
                raise OSError(f"等待受限进程失败：{wait}")
            time.sleep(0.01)
        if reason != "exited" and wait != 0 and not kernel.TerminateJobObject(job_handle, 1):
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
        if expected_source_sha is not None and runtime._sha256(source) != expected_source_sha:
            raise OSError("受限运行期间源码发生变化。")
        return {"phase": "build" if build else "solve", "pid": process.pid, "slot": slot["slot"],
                "logical_processor": logical, "identity": evidence, "job_flags": observed.basic.flags,
                "affinity": observed.basic.affinity, "resource_precheck": resources, "reason": reason,
                "exit_code": exit_code.value, "elapsed_seconds": completed - start,
                "resumed_monotonic": resumed, "finished_monotonic": completed,
                "cpu_seconds": (accounting.user + accounting.kernel) / 10_000_000,
                "stdout_bytes": readers[0].observed, "stderr_bytes": readers[1].observed,
                "stdout_b64": base64.b64encode(readers[0].data).decode("ascii"),
                "stderr_b64": base64.b64encode(readers[1].data).decode("ascii"), "input": input_result}
    finally:
        try:
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
        finally:
            if prepared_source is not None:
                prepared_source.__exit__(None, None, None)


def _candidate_paths(profile_name: str, folder: Path) -> tuple[Path, Path]:
    return ROOT / "outputs" / "p0_identity_claims", folder / "p0_candidate" / "solver.py"


def run_candidate(profile_name: str, slot_index: int, source: bytes, payload: bytes, *, build: bool) -> dict:
    """先验证任务3证据，再为一次构建或求解使用一个独立身份。"""
    plan = _require_gate()
    if (type(source) is not bytes or not source or len(source) > MAX_SOURCE_BYTES
            or type(payload) is not bytes or type(build) is not bool or (build and payload)):
        raise ValueError("源码、输入或构建模式无效。")
    mapping = job.select_mapping(*job.read_windows_topology())["workers"]
    if type(slot_index) is not int or not 0 <= slot_index < len(mapping):
        raise ValueError("槽位无效。")
    profile = _profile(plan, profile_name)
    folder = Path(profile["profile_folder"])
    claims, source_path = _candidate_paths(profile_name, folder)
    destination = source_path.parent
    expected = hashlib.sha256(source).hexdigest()
    claim_path = claims / f"{profile_name}.json"

    def prepare():
        # 在资源门禁通过后才占用身份；失败时保留已创建的记录，不覆盖或删除。
        claims.mkdir(exist_ok=True)
        runtime._safe_stat(claims)
        with claim_path.open("x", encoding="utf-8", newline="\n") as claim:
            json.dump({"profile_name": profile_name, "slot": slot_index, "phase": "build" if build else "solve",
                       "source_sha256": expected}, claim, ensure_ascii=True)
            claim.write("\n")
        destination.mkdir()
        runtime._safe_stat(destination)
        with source_path.open("xb") as stream:
            stream.write(source)
        locked = _LockedSource(source_path)
        locked.__enter__()
        try:
            if runtime._sha256(source_path) != expected:
                raise OSError("源码写入后摘要不一致。")
        except BaseException:
            locked.__exit__(None, None, None)
            raise
        return locked

    with _SlotGuard(slot_index):
        result = _run_program(profile, mapping[slot_index], source_path, payload, build=build,
                              prepare_source=prepare, expected_source_sha=expected)
    result.update({"profile_name": profile_name, "source_path": str(source_path), "source_sha256": expected,
                   "identity_claim": str(claim_path)})
    return result


def _network_probe(profiles: list[dict], slot: dict, source: Path, address: str, sink) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((address, 0))
        listener.listen(4)
        listener.settimeout(0.2)
        port = listener.getsockname()[1]
        connections, errors = [], []
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
                    connections.append(True)

        server = threading.Thread(target=serve, daemon=True)
        server.start()
        try:
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(connections) < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            before = len(connections)
            mode = "loopback" if address == "127.0.0.1" else "local_network"
            with _SlotGuard(slot["slot"]):
                result = _run_program(profiles[0], slot, source, b"", build=False, probe_mode=mode,
                                      other=profiles[1], port=port, network_address=address)
            sink({"event": "probe", "case": mode, "result": result})
            time.sleep(0.25)
            after = len(connections)
            with socket.create_connection((address, port), timeout=2):
                pass
            deadline = time.monotonic() + 2
            while len(connections) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            final = len(connections)
        finally:
            stop.set()
            server.join(timeout=3)
            if server.is_alive():
                errors.append("server_not_stopped")
    try:
        blocked = (result["reason"] == "exited" and result["exit_code"] == 0
                   and json.loads(base64.b64decode(result["stdout_b64"], validate=True)).get("connected") is False)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        blocked = False
    return {"address": address, "passed": blocked and (before, after, final) == (1, 1, 2) and not errors,
            "host_connection_counts": [before, after, final], "server_errors": errors}


def _probe_entry(plan: dict, sink) -> dict:
    """只以标准库中的固定源码检查实际文件入口，不运行候选。"""
    profiles = [_profile(plan, target["name"]) for target in plan["targets"]]
    if len(profiles) != 16 or len({item["profile_sid"] for item in profiles}) != 16:
        raise ValueError("测试身份不独立。")
    identity.PROFILE_RECORDS.update({target["name"]: Path(target["profile_record"]).name for target in plan["targets"]})
    slots_map = job.select_mapping(*job.read_windows_topology())["workers"]
    payload = {"probe": "stdin", "values": [1, 2, 3]}
    results = []
    for index, build in ((0, True), (1, False)):
        source = Path(profiles[index]["profile_folder"]) / identity.RUNTIME_DIR / "Lib" / "json" / "tool.py"
        for path in (source.parent.parent, source.parent, source):
            runtime._safe_stat(path)
        with _LockedSource(source):
            before = runtime._sha256(source)
            with _SlotGuard(slots_map[index]["slot"]):
                result = _run_program(profiles[index], slots_map[index], source,
                                      b"" if build else json.dumps(payload).encode("utf-8"), build=build)
            result["source_unchanged"] = runtime._sha256(source) == before
        results.append(result)
        sink({"event": "probe", "case": "build" if build else "file", "result": result})
    try:
        passed = (results[0]["reason"] == "exited" and results[0]["exit_code"] == 0
                  and base64.b64decode(results[0]["stdout_b64"], validate=True) == b""
                  and results[1]["reason"] == "exited" and results[1]["exit_code"] == 0
                  and json.loads(base64.b64decode(results[1]["stdout_b64"], validate=True)) == payload
                  and all(item["source_unchanged"] for item in results))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        passed = False
    if not passed:
        raise OSError("标准库文件构建或运行检查未通过。")
    source = Path(profiles[0]["profile_folder"]) / identity.RUNTIME_DIR / "Lib" / "json" / "tool.py"
    invalid_source = (Path(profiles[0]["profile_folder"]) / identity.RUNTIME_DIR / "Lib" / "test"
                      / "test_future_stmt" / "badsyntax_future.py")
    with _LockedSource(invalid_source), _SlotGuard(slots_map[0]["slot"]):
        invalid = _run_program(profiles[0], slots_map[0], invalid_source, b"", build=True)
    sink({"event": "probe", "case": "invalid_build", "result": invalid})
    if (invalid["reason"] != "exited" or invalid["exit_code"] == 0
            or b"SyntaxError" not in base64.b64decode(invalid["stderr_b64"], validate=True)):
        raise OSError("无效语法未按预期拒绝。")
    limits = {}
    for mode in ("stdout_limit", "stderr_limit", "timeout"):
        with _SlotGuard(slots_map[0]["slot"]):
            result = _run_program(profiles[0], slots_map[0], source, b"", build=False,
                                  probe_mode=mode, other=profiles[1])
        sink({"event": "probe", "case": mode, "result": result})
        limits[mode] = (result["reason"] == mode and result["exit_code"] != 0)
    if not all(limits.values()):
        raise OSError("输出上限或超时检查未通过。")

    protection = {}
    for mode in ("child_attempt", "affinity_attempt"):
        with _SlotGuard(slots_map[0]["slot"]):
            result = _run_program(profiles[0], slots_map[0], source, b"", build=False,
                                  probe_mode=mode, other=profiles[1])
        sink({"event": "probe", "case": mode, "result": result})
        try:
            report = json.loads(base64.b64decode(result["stdout_b64"], validate=True))
            if mode == "child_attempt":
                protection[mode] = (result["reason"] == "exited" and result["exit_code"] == 0
                                    and len(report) == 2 and report[0].get("created") is False
                                    and report[0].get("winerror") == 1816 and report[1].get("created") is False)
            else:
                expected = 1 << slots_map[0]["logical_processor"]
                protection[mode] = (result["reason"] == "exited" and result["exit_code"] == 0
                                    and report.get("before") == expected and report.get("after") == expected)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            protection[mode] = False
    if not all(protection.values()):
        raise OSError("子进程或绑定绕过检查未通过。")

    coordinates = [[0, 0], [1, 0], [1, 1], [0, 1]]
    instance = evaluator.make_solver_input(coordinates, seed=0, time_limit_ms=15000)
    with _SlotGuard(slots_map[0]["slot"]):
        tsp = _run_program(profiles[0], slots_map[0], source, json.dumps(instance).encode("utf-8"), build=False,
                           probe_mode="tsp_fixture", other=profiles[1])
    sink({"event": "probe", "case": "tsp_fixture", "result": tsp})
    if tsp["reason"] != "exited":
        raise OSError("固定TSP样例未正常退出。")
    checked = evaluator.evaluate_response(coordinates, base64.b64decode(tsp["stdout_b64"], validate=True),
                                          exit_code=tsp["exit_code"], elapsed_ms=tsp["elapsed_seconds"] * 1000,
                                          time_limit_ms=15000)
    if checked != {"valid": True, "objective": 4.0}:
        raise OSError("独立评价结果与手算样例不一致。")

    def run_hold(index):
        other = profiles[(index + 1) % 16]
        with _SlotGuard(slots_map[index]["slot"]):
            result = _run_program(profiles[index], slots_map[index], source, b"", build=False,
                                  probe_mode="hold", other=other)
        result["profile_name"] = profiles[index]["profile_name"]
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        holds = list(executor.map(run_hold, range(16)))
    for item in holds:
        sink({"event": "probe", "case": "parallel", "result": item})
    if not slots._parallel_passed(holds):
        raise OSError("实际入口的16身份并发或绑核未通过。")
    file_checks = []
    for index in (0, 1):
        for mode, expected in (("read_own_runtime", "read"), ("read_other_runtime", "denied"),
                               ("read_host", "denied")):
            with _SlotGuard(slots_map[index]["slot"]):
                result = _run_program(profiles[index], slots_map[index], source, b"", build=False,
                                      probe_mode=mode, other=profiles[1 - index])
            sink({"event": "probe", "case": mode, "result": result})
            file_checks.append(probe._read_result(result, expected))
    if not all(file_checks):
        raise OSError("实际入口的文件隔离检查未通过。")
    addresses = probe._local_private_ipv4()
    if not addresses:
        raise OSError("没有可核验的本机局域网地址。")
    networks = [_network_probe(profiles, slots_map[0], source, "127.0.0.1", sink),
                _network_probe(profiles, slots_map[0], source, addresses[0], sink)]
    return {"passed": all(item["passed"] for item in networks),
            "scope": "16个不同身份；标准库文件和固定无害探针，不运行候选。",
            "limits": limits, "protection": protection, "tsp_fixture": checked,
            "parallel_passed": True, "file_checks": file_checks, "network_checks": networks}


def main() -> int:
    parser = argparse.ArgumentParser(description="仅运行P0受限入口的固定无害探针。")
    parser.add_argument("--probe", action="store_true", required=True)
    parser.add_argument("--record", required=True, help="outputs 中新建 p0_task3_executor_probe_*.jsonl")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_executor_probe_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名无效。")
    path = ROOT / "outputs" / options.record
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        result = {"passed": False}
        try:
            plan = _slot_evidence()
            save({"event": "sources", "executor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "slot_record_sha256": hashlib.sha256(SLOT_RECORD.read_bytes()).hexdigest()})
            result = _probe_entry(plan, save)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            save({"event": "error", "message": f"{type(exc).__name__}: {exc}"})
            result["error"] = f"{type(exc).__name__}: {exc}"
        save({"event": "result", "result": result})
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
