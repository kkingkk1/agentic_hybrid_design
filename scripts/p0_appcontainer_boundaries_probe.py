"""只检查一个自建 AppContainer 身份对模拟文件和本机回环的访问。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time

if __package__:
    from . import p0_appcontainer_probe as identity
    from . import p0_job_probe as job
else:
    import p0_appcontainer_probe as identity
    import p0_job_probe as job


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RECORD = "p0_task3_appcontainer_profile_20261105_01.jsonl"
PROFILE_NAME = "P0Task3Probe_20261105_01"
FIXTURE_TEXT = "P0 simulated sensitive data; not a real secret.\n"
FIRST_BOUNDARY_RECORD = "p0_task3_appcontainer_boundary_20261105_01.jsonl"
FIRST_OWN_RECORD = "p0_task3_appcontainer_boundary_own_20261105_01.jsonl"


def _loopback_blocked(probe: dict, host_before: int, host_after: int,
                      count_before: int, count_after: int, count_final: int, server_errors: list) -> bool:
    return (host_before == host_after == 0 and (count_before, count_after, count_final) == (1, 1, 2)
            and not server_errors and probe.get("identity_verified") is True
            and probe.get("stage") == "completed" and probe.get("exit_code") in (7, 28))


def run_own_fixture_probe(sink=None) -> dict:
    """在已授权身份自己的目录新建模拟文件，检查该身份能否读取。"""
    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "scope": "仅验证指定身份能否读取其目录内的自建模拟文件。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(PROFILE_RECORD)
        if profile["profile_name"] != PROFILE_NAME:
            raise ValueError("创建记录不是获授权的测试身份。")
        sink({"event": "profile_source", "record": PROFILE_RECORD, "sha256": profile["source_record_sha256"]})
        fixture = Path(profile["profile_folder"]) / identity.OWN_FIXTURE_NAME
        with fixture.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(FIXTURE_TEXT)
        sink({"event": "own_fixture_created", "path": str(fixture)})
        if fixture.read_text(encoding="utf-8") != FIXTURE_TEXT:
            raise OSError("宿主无法核对自建模拟文件。")
        result["fixture_path"] = str(fixture)
        result["probe"] = identity.run_probe(reused_profile=profile, action="own_fixture")
        result["passed"] = result["probe"].get("passed") is True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_python_probe(sink=None) -> dict:
    """只运行已选解释器的版本命令，不加载或运行候选代码。"""
    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "scope": "仅检查指定身份能否启动已选的 Python 3.13.12。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(PROFILE_RECORD)
        if profile["profile_name"] != PROFILE_NAME:
            raise ValueError("创建记录不是获授权的测试身份。")
        sink({"event": "profile_source", "record": PROFILE_RECORD, "sha256": profile["source_record_sha256"]})
        root = os.environ.get("SystemRoot", r"C:\Windows")
        environment = {"SystemRoot": root, "WINDIR": root, "PATH": os.path.join(root, "System32")}
        host = subprocess.run([sys.executable, "-I", "-B", "-V"], env=environment, capture_output=True,
                              creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
        result["host_exit"] = host.returncode
        result["host_version"] = (host.stdout or host.stderr).decode("ascii", errors="replace").strip()
        if host.returncode != 0 or result["host_version"] != "Python 3.13.12":
            raise OSError("宿主解释器版本不符合P0合同。")
        system_dir = os.path.join(root, "System32")
        executable, command = identity._controlled_command(system_dir, "python_version")
        host_shell = subprocess.run(command, executable=executable, cwd=system_dir, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
        result["host_command_exit"] = host_shell.returncode
        result["host_command_version"] = (host_shell.stdout or host_shell.stderr).decode(
            "ascii", errors="replace").strip()
        if result["host_command_exit"] != 0 or result["host_command_version"] != "Python 3.13.12":
            raise OSError("宿主使用相同命令的版本对照失败。")
        result["output_control"] = identity.run_probe(reused_profile=profile, action="output_control")
        if result["output_control"].get("passed") is not True:
            raise OSError("身份的输出对照失败。")
        result["python_probe"] = identity.run_probe(reused_profile=profile, action="python_version")
        result["passed"] = result["python_probe"].get("passed") is True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_direct_runtime_probe(sink=None, recheck: int = 0) -> dict:
    """复核已复制文件后，直接以AppContainer身份启动固定的标准库自检。"""
    if sink is None:
        sink = lambda _event: None
    if __package__:
        from . import p0_sandbox_runtime as runtime
    else:
        import p0_sandbox_runtime as runtime
    result = {"passed": False, "scope": "仅直接启动第一份已授权复制的Python并导入固定标准库。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(PROFILE_RECORD)
        if profile["profile_name"] != PROFILE_NAME:
            raise ValueError("创建记录不是获授权的测试身份。")
        manifest = json.loads(runtime.MANIFEST.read_bytes())
        destination = Path(profile["profile_folder"]) / identity.RUNTIME_DIR
        prior_hash = runtime._verify_resume_record(destination, manifest)
        count = runtime._verify_copied(destination, manifest)
        sink({"event": "destination_reverified", "path": str(destination), "verified_files": count,
              "previous_record_sha256": prior_hash})
        result["verified_files"] = count
        action = {0: "owned_python_direct", 1: "owned_python_direct_recheck",
                  2: "owned_python_direct_recheck2"}[recheck]
        result["probe"] = identity.run_probe(reused_profile=profile, action=action)
        result["passed"] = result["probe"].get("passed") is True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_combined_job_probe(sink=None) -> dict:
    """在现有测试身份中运行固定探针，不接受候选源码或外部命令。"""
    if sink is None:
        sink = lambda _event: None
    if __package__:
        from . import p0_sandbox_runtime as runtime
    else:
        import p0_sandbox_runtime as runtime
    result = {"passed": False, "scope": "仅组合检查既有身份、单进程、单逻辑处理器、固定语法编译和超时终止。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(PROFILE_RECORD)
        if profile["profile_name"] != PROFILE_NAME:
            raise ValueError("创建记录不是获授权的测试身份。")
        manifest = json.loads(runtime.MANIFEST.read_bytes())
        destination = Path(profile["profile_folder"]) / identity.RUNTIME_DIR
        prior_hash = runtime._verify_resume_record(destination, manifest)
        count = runtime._verify_copied(destination, manifest)
        sink({"event": "destination_reverified", "path": str(destination), "verified_files": count,
              "previous_record_sha256": prior_hash})
        result["verified_files"] = count
        result["probe"] = identity.run_probe(reused_profile=profile, action="owned_python_job")
        if result["probe"].get("passed") is not True:
            raise OSError("组合探针未通过，不启动超时探针。")
        result["timeout_resource_precheck"] = job._resource_gate()
        result["timeout_probe"] = identity.run_probe(reused_profile=profile, action="owned_python_job_timeout")
        result["passed"] = result["timeout_probe"].get("passed") is True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_cross_fixture_probe(sink=None) -> dict:
    """只检查两个指定身份对各自及对方模拟文件的读取，不修改 ACL。"""
    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "scope": "只核验两个自建身份的双向模拟文件访问。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profiles = [identity._recorded_profile(record) for record in identity.PROFILE_RECORDS.values()]
        if ([item["profile_name"] for item in profiles] != list(identity.PROFILE_RECORDS)
                or profiles[0]["profile_sid"] == profiles[1]["profile_sid"]):
            raise ValueError("两个测试身份不匹配或不独立。")
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            raise OSError("缺少 LOCALAPPDATA，不能核对身份目录。")
        for profile in profiles:
            expected = Path(local_appdata) / "Packages" / profile["profile_name"].lower() / "AC"
            actual = Path(profile["profile_folder"])
            if os.path.normcase(os.path.normpath(actual)) != os.path.normcase(os.path.normpath(expected)):
                raise ValueError("测试身份目录与当前用户的预期目录不一致。")
            if actual.stat().st_file_attributes & 0x400:
                raise ValueError("测试身份目录是重解析点，停止探针。")
        previous = (ROOT / "outputs" / FIRST_OWN_RECORD).read_bytes()
        if len(previous) > 65536:
            raise ValueError("自有模拟文件来源记录过大。")
        events = [json.loads(line) for line in previous.splitlines()]
        created = [event for event in events if event.get("event") == "own_fixture_created"]
        prior_results = [event.get("result", {}) for event in events if event.get("event") == "result"]
        first_file = Path(profiles[0]["profile_folder"]) / identity.OWN_FIXTURE_NAME
        if (len(created) != 1 or created[0].get("path") != str(first_file)
                or len(prior_results) != 1 or prior_results[0].get("passed") is not True
                or first_file.read_text(encoding="utf-8") != FIXTURE_TEXT):
            raise ValueError("第一个身份的模拟文件和成功记录无法核实。")
        sink({"event": "first_fixture_source", "record": FIRST_OWN_RECORD,
              "sha256": hashlib.sha256(previous).hexdigest()})
        second_file = Path(profiles[1]["profile_folder"]) / identity.OWN_FIXTURE_NAME
        with second_file.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(FIXTURE_TEXT)
        sink({"event": "second_fixture_created", "path": str(second_file)})
        if second_file.read_text(encoding="utf-8") != FIXTURE_TEXT:
            raise OSError("宿主无法核对第二个模拟文件。")
        result["profiles"] = []
        for profile in profiles:
            output_control = identity.run_probe(reused_profile=profile, action="output_control")
            own = identity.run_probe(reused_profile=profile, action="own_fixture")
            other = identity.run_probe(reused_profile=profile, action="other_fixture")
            blocked = (other.get("identity_verified") is True and other.get("stage") == "completed"
                       and other.get("exit_code") == 1)
            result["profiles"].append({"name": profile["profile_name"], "output_control": output_control,
                                       "own_fixture": own, "other_fixture": other, "other_blocked": blocked})
        result["passed"] = all(item["output_control"].get("passed") is True
                               and item["own_fixture"].get("passed") is True and item["other_blocked"]
                               for item in result["profiles"])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def run_probe(sink=None, reuse_fixture: bool = False) -> dict:
    """不接收任意命令、文件或网络地址，也不修改现有 ACL。"""
    if sink is None:
        sink = lambda _event: None
    result = {"passed": False, "scope": "仅验证一个身份对自建模拟文件和本机回环的访问。"}
    try:
        result["resource_precheck"] = job._resource_gate()
        profile = identity._recorded_profile(PROFILE_RECORD)
        if profile["profile_name"] != PROFILE_NAME:
            raise ValueError("创建记录不是获授权的测试身份。")
        sink({"event": "profile_source", "record": PROFILE_RECORD, "sha256": profile["source_record_sha256"]})
        fixture = identity.BOUNDARY_FIXTURE
        if reuse_fixture:
            original = (ROOT / "outputs" / FIRST_BOUNDARY_RECORD).read_bytes()
            if len(original) > 65536:
                raise ValueError("模拟文件来源记录过大。")
            events = [json.loads(line) for line in original.splitlines()]
            matches = [event for event in events if event.get("event") == "fixture_created"]
            if len(matches) != 1 or matches[0].get("path") != str(fixture):
                raise ValueError("无法核实模拟文件的创建来源。")
            sink({"event": "fixture_reused", "path": str(fixture), "record": FIRST_BOUNDARY_RECORD,
                  "sha256": hashlib.sha256(original).hexdigest()})
        else:
            with fixture.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(FIXTURE_TEXT)
            sink({"event": "fixture_created", "path": str(fixture)})
        if fixture.read_text(encoding="utf-8") != FIXTURE_TEXT:
            raise OSError("无法由宿主核对自建模拟文件。")

        root = os.environ.get("SystemRoot", r"C:\Windows")
        system_dir = os.path.join(root, "System32")
        executable, command = identity._controlled_command(system_dir, "fixture")
        environment = {"SystemRoot": root, "WINDIR": root, "PATH": system_dir}
        host = subprocess.run(command, executable=executable, cwd=system_dir, env=environment,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
        result["host_fixture_exit"] = host.returncode
        if host.returncode != 0:
            raise OSError("宿主对照无法读取模拟文件，不能判断隔离。")

        positive = identity.run_probe(reused_profile=profile)
        result["identity_control"] = positive
        if not positive.get("passed"):
            raise OSError("AppContainer身份对照未通过。")
        output_control = identity.run_probe(reused_profile=profile, action="output_control")
        result["output_control"] = output_control
        if not output_control.get("passed"):
            raise OSError("AppContainer输出对照未通过，不能判断模拟文件访问。")
        file_probe = identity.run_probe(reused_profile=profile, action="fixture")
        result["fixture_probe"] = file_probe
        result["fixture_blocked"] = (file_probe.get("identity_verified") is True
                                     and file_probe.get("stage") == "completed"
                                     and file_probe.get("exit_code") == 1)

        curl_control = identity.run_probe(reused_profile=profile, action="curl_version")
        result["curl_control"] = curl_control
        if not curl_control.get("passed"):
            raise OSError("AppContainer中的curl无网络对照未通过。")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(4)
            listener.settimeout(0.2)
            port = listener.getsockname()[1]
            requests, server_errors = [], []
            stop_server = threading.Event()

            def serve():
                while not stop_server.is_set():
                    try:
                        connection, _ = listener.accept()
                    except socket.timeout:
                        continue
                    except OSError as exc:
                        if not stop_server.is_set():
                            server_errors.append(type(exc).__name__)
                        return
                    with connection:
                        try:
                            connection.settimeout(2)
                            request = connection.recv(2048)
                            if not request.startswith(b"GET /p0 HTTP/"):
                                server_errors.append("unexpected_request")
                            requests.append(True)  # 不保存客户端地址或请求内容。
                            connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
                        except OSError as exc:
                            server_errors.append(type(exc).__name__)

            server = threading.Thread(target=serve, name="p0-owned-loopback", daemon=True)
            server.start()
            try:
                executable, command = identity._controlled_command(system_dir, "loopback", port)

                def host_loopback():
                    return subprocess.run(command, executable=executable, cwd=system_dir, env=environment,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
                                          check=False).returncode

                host_before = host_loopback()
                count_before = len(requests)
                network_probe = identity.run_probe(reused_profile=profile, action="loopback", port=port)
                time.sleep(0.25)  # 让自建监听器完成已进入队列的连接。
                count_after = len(requests)
                host_after = host_loopback()
                count_final = len(requests)
            finally:
                stop_server.set()
                server.join(timeout=3)
                if server.is_alive():
                    server_errors.append("server_not_stopped")
            result.update({"loopback_probe": network_probe, "host_loopback_exit_before": host_before,
                           "host_loopback_exit_after": host_after, "request_counts": [count_before, count_after,
                                                                                     count_final],
                           "server_errors": server_errors})
            result["loopback_blocked"] = _loopback_blocked(network_probe, host_before, host_after, count_before,
                                                           count_after, count_final, server_errors)
        result["passed"] = result["fixture_blocked"] and result["loopback_blocked"]
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="只验证自建模拟文件和本机回环，不运行候选。")
    parser.add_argument("--record", required=True, help="outputs 中新建 p0_task3_appcontainer_boundary_*.jsonl")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reuse-fixture", action="store_true", help="验证首次记录后只读复用同一模拟文件")
    mode.add_argument("--own-fixture-only", action="store_true", help="仅检查身份对自己目录中模拟文件的访问")
    mode.add_argument("--cross-fixture-only", action="store_true", help="仅检查两个已授权身份的双向模拟文件访问")
    mode.add_argument("--python-version-only", action="store_true", help="仅检查已选解释器能否输出版本")
    mode.add_argument("--direct-runtime-only", action="store_true", help="仅检查首份复制运行时的直接启动")
    mode.add_argument("--direct-runtime-recheck", action="store_true", help="复核运行时版本及模块来源")
    mode.add_argument("--direct-runtime-recheck2", action="store_true", help="复核内建模块及其余模块来源")
    mode.add_argument("--combined-job-only", action="store_true", help="只组合检查已授权身份和单处理器作业")
    options = parser.parse_args()
    if not re.fullmatch(r"p0_task3_appcontainer_boundary_[a-z0-9_]+\.jsonl", options.record):
        parser.error("记录名须为 p0_task3_appcontainer_boundary_*.jsonl，且不能包含路径。")
    with (ROOT / "outputs" / options.record).open("x", encoding="utf-8", newline="\n") as stream:
        def save(event):
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
            stream.flush()
        sources = [Path(__file__), ROOT / "scripts" / "p0_appcontainer_probe.py",
                   ROOT / "scripts" / "p0_job_probe.py", ROOT / "scripts" / "p0_sandbox_runtime.py"]
        save({"event": "sources", "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                                for path in sources}})
        try:
            if options.own_fixture_only:
                result = run_own_fixture_probe(save)
            elif options.cross_fixture_only:
                result = run_cross_fixture_probe(save)
            elif options.python_version_only:
                result = run_python_probe(save)
            elif options.direct_runtime_only:
                result = run_direct_runtime_probe(save)
            elif options.direct_runtime_recheck:
                result = run_direct_runtime_probe(save, recheck=1)
            elif options.direct_runtime_recheck2:
                result = run_direct_runtime_probe(save, recheck=2)
            elif options.combined_job_only:
                result = run_combined_job_probe(save)
            else:
                result = run_probe(save, options.reuse_fixture)
        except Exception as exc:
            result = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        save({"event": "result", "result": result})
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
