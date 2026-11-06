"""P0 模型调用的本地检查、受限进程和原始事件监督。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time

if __package__:
    from . import p0_job_probe as job
else:
    import p0_job_probe as job


MODEL = "gpt-5.6-luna"
VERSION = "codex-cli 0.163.0"
MAX_MODEL_BYTES = 1024 * 1024
DISABLED = ("shell_tool", "unified_exec", "unbounded_connection_retries", "hooks", "plugins", "apps",
            "daemon_auto_start", "shell_snapshot")
FEATURE_ARGS = [item for feature in DISABLED for item in ("--disable", feature)]
PROVIDER_ARGS = [
    "-c", 'model_provider="p0_chatgpt_https"',
    "-c", 'model_providers.p0_chatgpt_https.name="OpenAI"',
    "-c", 'model_providers.p0_chatgpt_https.base_url="https://chatgpt.com/backend-api/codex"',
    "-c", "model_providers.p0_chatgpt_https.requires_openai_auth=true",
    "-c", "model_providers.p0_chatgpt_https.supports_websockets=false",
    "-c", 'model_providers.p0_chatgpt_https.wire_api="responses"',
    "-c", "model_providers.p0_chatgpt_https.request_max_retries=0",
    "-c", "model_providers.p0_chatgpt_https.stream_max_retries=0",
]


class ModelError(RuntimeError):
    """模型调用、进程边界或用量不能按合同确认。"""


class ResponseFormatError(ModelError):
    """用量完整但模型响应格式不符合合同。"""

    def __init__(self, message: str, usage: dict):
        super().__init__(message)
        self.usage = usage


def executable() -> Path:
    """定位 npm 包实际启动的原生程序，避免包装进程占用作业名额。"""
    command = shutil.which("codex.cmd")
    if not command:
        raise ModelError("找不到现有 Codex CLI。")
    root = Path(command).parent / "node_modules" / "@openai" / "codex"
    binary = (root / "node_modules" / "@openai" / "codex-win32-x64" / "vendor"
              / "x86_64-pc-windows-msvc" / "bin" / "codex.exe")
    if not binary.is_file():
        raise ModelError("找不到当前 Codex 包的原生程序。")
    return binary.resolve()


def child_environment() -> dict[str, str]:
    """保留现有登录位置与代理，不向 CLI 传递 API key 环境变量。"""
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "PATH", "PROGRAMDATA", "USERPROFILE",
               "HOMEDRIVE", "HOMEPATH", "HOME", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "CODEX_HOME",
               "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class EventAudit:
    """实时拒绝工具事件、错误事件和不可核实的重连。"""

    def __init__(self):
        self.buffer = b""
        self.events: list[dict] = []

    def feed(self, chunk: bytes) -> None:
        self.buffer += chunk
        if len(self.buffer) > MAX_MODEL_BYTES:
            raise ModelError("单个模型事件超过输出上限。")
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                event = json.loads(line, object_pairs_hook=_unique_object)
            except (UnicodeDecodeError, ValueError) as exc:
                raise ModelError("模型事件不是有效 JSON。") from exc
            if type(event) is not dict:
                raise ModelError("模型事件不是对象。")
            kind = event.get("type")
            if kind not in {"thread.started", "turn.started", "item.started", "item.updated", "item.completed",
                            "turn.completed"}:
                raise ModelError("出现模型错误、重连或未预期的事件。")
            if kind.startswith("item."):
                item = event.get("item")
                if type(item) is not dict or item.get("type") not in {"agent_message", "reasoning"}:
                    raise ModelError("模型请求了非预期工具或动作。")
            self.events.append(event)

    def finish(self) -> tuple[dict, dict]:
        if self.buffer.strip():
            raise ModelError("模型事件流不完整。")
        completed = [event for event in self.events if event.get("type") == "turn.completed"]
        messages = [event["item"].get("text") for event in self.events
                    if event.get("type") == "item.completed" and event["item"].get("type") == "agent_message"]
        if len(completed) != 1 or len(messages) != 1 or type(messages[0]) is not str:
            raise ModelError("模型未返回唯一的最终消息与用量。")
        usage = completed[0].get("usage")
        if (type(usage) is not dict or any(type(usage.get(key)) is not int or usage[key] < 0
                                            for key in ("input_tokens", "output_tokens"))):
            raise ModelError("模型用量缺失或无效，不能继续调用。")
        try:
            response = json.loads(messages[0], object_pairs_hook=_unique_object,
                                  parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite")))
        except (ValueError, RecursionError) as exc:
            raise ResponseFormatError("模型最终消息不是有效 JSON。", usage) from exc
        if (type(response) is not dict or set(response) != {"thought", "code"}
                or any(type(response[key]) is not str or not response[key].strip() for key in ("thought", "code"))):
            raise ResponseFormatError("模型响应不符合 thought/code 合同。", usage)
        if len(messages[0].encode("utf-8")) > MAX_MODEL_BYTES:
            raise ModelError("模型响应超过 1 MiB。")
        return response, usage


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def limited_process(command: list[str], out_path: Path, err_path: Path, *, stdin: bytes = b"",
                    deadline: float, audit: EventAudit | None = None) -> dict:
    """直接启动原生程序；恢复之前验证单进程、禁止 breakaway 的作业限制。"""
    kernel, ntdll = job._apis()
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    process = None
    assigned = False
    started = time.monotonic()
    reason = "exited"
    accounting = job.Accounting()
    try:
        limits = job.ExtendedLimits()
        limits.basic.flags = 0x0008 | 0x2000
        limits.basic.active_limit = 1
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        with out_path.open("xb") as out, err_path.open("xb") as err:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err, shell=False,
                                       env=child_environment(), cwd=str(out_path.parent),
                                       creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW
                                       | subprocess.NORMAL_PRIORITY_CLASS)
            if not kernel.AssignProcessToJobObject(handle, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            assigned = True
            observed = job.ExtendedLimits()
            if not kernel.QueryInformationJobObject(handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if (observed.basic.active_limit != 1 or observed.basic.flags & (0x0008 | 0x2000) != (0x0008 | 0x2000)
                    or observed.basic.flags & (0x0800 | 0x1000)):
                raise ModelError("模型进程的作业限制不符合合同。")
            if ntdll.NtResumeProcess(int(process._handle)) != 0:
                raise ModelError("无法恢复受限模型进程。")
            try:
                process.stdin.write(stdin)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                reason = "input_error"
            with out_path.open("rb") as reader, err_path.open("rb") as errors:
                err_tail = b""
                while True:
                    chunk = reader.read()
                    if audit is not None and chunk:
                        try:
                            audit.feed(chunk)
                        except ModelError as exc:
                            reason = str(exc)
                    error_chunk = errors.read()
                    err_tail = (err_tail + error_chunk)[-4096:]
                    if audit is not None and re.search(rb"reconnect|retrying|waiting to retry|falling back from websocket",
                                                       err_tail, flags=re.IGNORECASE):
                        reason = "检测到模型重连或重试。"
                    if out_path.stat().st_size > (MAX_MODEL_BYTES if audit is not None else 8 * MAX_MODEL_BYTES):
                        reason = "模型标准输出超过上限。"
                    if err_path.stat().st_size > MAX_MODEL_BYTES:
                        reason = "模型标准错误超过上限。"
                    if time.monotonic() >= deadline:
                        reason = "超过本批墙钟上限。"
                    if reason != "exited":
                        if process.poll() is None:
                            kernel.TerminateJobObject(handle, 1)
                        break
                    if process.poll() is not None:
                        # 退出后再读一次，避免丢失最后一个事件。
                        final = reader.read()
                        if audit is not None and final:
                            try:
                                audit.feed(final)
                            except ModelError as exc:
                                reason = str(exc)
                        err_tail = (err_tail + errors.read())[-4096:]
                        if audit is not None and re.search(rb"reconnect|retrying|waiting to retry|falling back from websocket",
                                                           err_tail, flags=re.IGNORECASE):
                            reason = "检测到模型重连或重试。"
                        if out_path.stat().st_size > (MAX_MODEL_BYTES if audit is not None else 8 * MAX_MODEL_BYTES):
                            reason = "模型标准输出超过上限。"
                        if err_path.stat().st_size > MAX_MODEL_BYTES:
                            reason = "模型标准错误超过上限。"
                        break
                    time.sleep(0.05)
            exit_code = process.wait(timeout=5)
            if not kernel.QueryInformationJobObject(handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return {"pid": process.pid, "exit_code": exit_code, "reason": reason,
                    "elapsed_seconds": time.monotonic() - started,
                    "cpu_seconds": (accounting.user + accounting.kernel) / 10_000_000,
                    "job_flags": observed.basic.flags, "active_process_limit": observed.basic.active_limit}
    finally:
        if process is not None and process.poll() is None:
            if assigned:
                kernel.TerminateJobObject(handle, 1)
            else:
                process.kill()
            process.wait(timeout=5)
        kernel.CloseHandle(handle)


def command(binary: Path, work: Path, schema: Path) -> list[str]:
    return [str(binary), "exec", "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--json",
            "--sandbox", "read-only", "--model", MODEL, "--output-schema", str(schema),
            *FEATURE_ARGS, *PROVIDER_ARGS, "--cd", str(work), "-"]


def local_preflight(directory: Path) -> dict:
    """无模型调用地检查原生 CLI、功能开关与受限作业。"""
    binary = executable()
    cases = {
        "version": [str(binary), "--version"],
        "features": [str(binary), "features", "list", *FEATURE_ARGS],
        "exec_help": [str(binary), "exec", "--help"],
        "models": [str(binary), "debug", "models", "--bundled"],
        "login": [str(binary), "login", "status"],
    }
    results = {}
    for name, args in cases.items():
        out = directory / f"{name}.stdout"
        err = directory / f"{name}.stderr"
        result = limited_process(args, out, err, deadline=time.monotonic() + 30)
        if result["reason"] != "exited" or result["exit_code"] != 0:
            raise ModelError(f"原生 CLI 受限检查失败：{name}。")
        results[name] = result
    if (directory / "version.stdout").read_text(encoding="utf-8").strip() != VERSION:
        raise ModelError("原生 CLI 版本与 P0 合同不一致。")
    login_output = ((directory / "login.stdout").read_text(encoding="utf-8")
                    + (directory / "login.stderr").read_text(encoding="utf-8"))
    if "Logged in using ChatGPT" not in login_output:
        raise ModelError("当前 CLI 未确认使用 ChatGPT 登录。")
    features = {}
    for line in (directory / "features.stdout").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(\S+)\s+.+\s+(true|false)\s*$", line)
        if match:
            features[match.group(1)] = match.group(2) == "true"
    if any(features.get(name) is not False for name in DISABLED if name != "unified_exec"):
        raise ModelError("模型进程的工具、服务或重试开关未关闭。")
    catalog = json.loads((directory / "models.stdout").read_bytes())
    if len([model for model in catalog.get("models", []) if model.get("slug") == MODEL]) != 1:
        raise ModelError("本机模型目录未唯一列出合同模型。")
    help_text = (directory / "exec_help.stdout").read_text(encoding="utf-8")
    if any(flag not in help_text for flag in ("--ignore-user-config", "--output-schema", "--ephemeral", "--json")):
        raise ModelError("当前 CLI 缺少合同要求的调用参数。")
    return {"executable": str(binary), "version": VERSION, "bundled_model": MODEL,
            "disabled_features": {name: features.get(name) for name in DISABLED},
            "unified_exec_note": "该版本未关闭 unified_exec；由单进程作业限制和事件监督约束。",
            "process_checks": results}


def quota(binary: Path) -> dict:
    """只读订阅额度；不保存账户标识或原始响应。"""
    cmd = [str(binary), "app-server", *FEATURE_ARGS, *PROVIDER_ARGS]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding="utf-8", errors="replace", env=child_environment(),
                               creationflags=subprocess.CREATE_NO_WINDOW)
    lines: queue.Queue[str | None] = queue.Queue()

    def collect():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=collect, daemon=True).start()

    def send(value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()

    def receive(request_id):
        end = time.monotonic() + 40
        while time.monotonic() < end:
            try:
                line = lines.get(timeout=max(0.1, end - time.monotonic()))
            except queue.Empty as exc:
                raise ModelError("额度查询超时。") from exc
            if line is None:
                raise ModelError("额度查询进程提前结束。")
            event = json.loads(line)
            if type(event) is dict and event.get("id") == request_id:
                if "error" in event or type(event.get("result")) is not dict:
                    raise ModelError("额度查询返回错误。")
                return event["result"]
        raise ModelError("额度查询超时。")

    try:
        send({"method": "initialize", "id": 1, "params": {"clientInfo": {
            "name": "p0_task4", "title": "P0 quota check", "version": "1"}}})
        receive(1)
        send({"method": "initialized", "params": {}})
        send({"method": "account/rateLimits/read", "id": 2})
        data = receive(2)
        buckets = data.get("rateLimitsByLimitId") or {"default": data.get("rateLimits")}
        if data.get("ordinaryUsageAllowed") is not True or type(buckets) is not dict:
            raise ModelError("订阅未确认当前允许普通调用。")
        windows = []
        for bucket in buckets.values():
            if type(bucket) is not dict:
                raise ModelError("订阅额度格式无效。")
            if bucket.get("spendControlReached") is True or bucket.get("rateLimitReachedType") is not None:
                raise ModelError("订阅额度或支出限制已触发。")
            for key in ("primary", "secondary"):
                window = bucket.get(key)
                if window is None:
                    continue
                used = window.get("usedPercent") if type(window) is dict else None
                if type(used) not in (int, float) or not 0 <= used < 100:
                    raise ModelError("订阅额度窗口不可用或格式无效。")
                windows.append({"window": key, "used_percent": used, "duration_minutes": window.get("windowDurationMins"),
                                "resets_at_unix": window.get("resetsAt")})
        if not windows:
            raise ModelError("订阅没有可核验的额度窗口。")
        return {"ordinary_usage_allowed": True, "windows": windows, "remaining_model_calls": None,
                "scope": "订阅窗口只读快照，不能换算为剩余模型调用次数。"}
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
