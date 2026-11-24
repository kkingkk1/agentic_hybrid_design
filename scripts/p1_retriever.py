"""用固定快照的候选目录执行 Retriever 初选。"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any

from .p1_library_reader import HASH_PATTERN, LibraryError, RetrievalSnapshot


INITIAL_SELECTION_PROMPT = """\
You are the Retriever in the initialization phase of hybrid algorithm design.
Use problem_analysis and both complete catalogs in the input to select entries
worth reviewing in full. Preserve the problem's objective and feasible region.

Evaluate algorithms and cases independently. Use each algorithm's summary to
identify a reusable method or component. Use each case's description to identify
how components connect, exchange solutions or representations, or use feedback.
Treat categories as context. For every choice, identify a specific mechanism
described in the catalog and explain how it serves a current design need.
General knowledge can help interpret the input. Ground claims about an entry
in its own catalog text.

For an entry with clear relevance, flag only unresolved conditions that affect
the proposed use. When a known limitation allows partial reuse, state the
scope of that reuse and the adaptation it would require. A group can be empty
if its entries lack enough evidence of a concrete use. Select only entries
with sufficient grounds for follow-up review.

Return a single JSON object with exactly two array fields, algorithms and
cases, even when one or both arrays are empty. Each item must contain exactly
id and reason. Copy id verbatim from algorithm_id or case_id in the
corresponding catalog. Use each id at most once in its group. Write a brief,
nonblank reason for each choice. Return only JSON without Markdown or
duplicate keys."""


class RetrieverError(RuntimeError):
    """检索失败，本次结果无法交接。"""


def _catalog_version(events: Sequence[dict[str, Any]]) -> dict[str, str]:
    return _read_version(events, "catalog")


def _read_version(events: Sequence[dict[str, Any]], operation: str) -> dict[str, str]:
    reads = [event for event in events if event.get("operation") == operation]
    label = "目录" if operation == "catalog" else "全文"
    if len(reads) != 1 or reads[0].get("status") != "ok":
        raise RetrieverError(f"未取得本次{label}读取的唯一成功事件")
    snapshot_id = reads[0].get("snapshot_id")
    manifest_sha256 = reads[0].get("manifest_sha256")
    if (not isinstance(snapshot_id, str) or not snapshot_id.strip()
            or not isinstance(manifest_sha256, str) or not HASH_PATTERN.fullmatch(manifest_sha256)):
        raise RetrieverError(f"{label}读取事件缺少有效的快照标识或清单 SHA-256")
    return {"snapshot_id": snapshot_id, "manifest_sha256": manifest_sha256}


def _encode_request(prompt: str, payload: dict[str, Any], label: str) -> str:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        submitted = json.loads(encoded)
    except (TypeError, ValueError, RecursionError) as exc:
        raise RetrieverError(f"无法将{label}组装为 JSON 请求") from exc
    if submitted != payload:
        raise RetrieverError(f"待提交的 JSON 与{label}不一致")
    return f"{prompt}\n\nInput JSON\n{encoded}"


def _build_request(problem_analysis: dict[str, Any], catalog: dict[str, list[dict[str, Any]]]) -> str:
    if not isinstance(problem_analysis, dict):
        raise RetrieverError("问题分析必须是 JSON 对象")
    payload = {"problem_analysis": problem_analysis, "algorithms": catalog["algorithms"], "cases": catalog["cases"]}
    return _encode_request(INITIAL_SELECTION_PROMPT, payload, "完整问题分析或候选目录")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RetrieverError(f"模型响应 JSON 包含重复键 {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise RetrieverError(f"模型响应 JSON 含非有限数值 {value}")


def _decode_response(response: str) -> Any:
    try:
        return json.loads(response, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise RetrieverError("模型响应无法解析为 JSON") from exc


def _call_model(model_call: Callable[[str], str], request: str) -> str:
    try:
        response = model_call(request)
    except Exception as exc:
        raise RetrieverError(f"模型调用失败（{type(exc).__name__}）") from exc
    if not isinstance(response, str):
        raise RetrieverError("模型调用必须返回原始响应文本")
    return response


def _model_config(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or any(
        not isinstance(config.get(key), str) or not config[key].strip() for key in ("model", "version")
    ):
        raise RetrieverError("模型配置必须包含非空的 model 和 version")
    try:
        frozen = json.loads(json.dumps(config, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as exc:
        raise RetrieverError("模型配置必须可序列化为 JSON") from exc
    if frozen != config:
        raise RetrieverError("模型配置序列化后发生变化")
    return frozen


def _parse_selection(
    response: str, catalog: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any], list[str]]:
    selection = _decode_response(response)
    if not isinstance(selection, dict) or set(selection) != {"algorithms", "cases"}:
        raise RetrieverError("模型响应必须是仅含 algorithms 和 cases 的 JSON 对象")

    selected_ids = []
    for group, id_key in (("algorithms", "algorithm_id"), ("cases", "case_id")):
        items = selection[group]
        if not isinstance(items, list):
            raise RetrieverError(f"{group} 必须是数组")
        allowed_ids = {entry[id_key] for entry in catalog[group]}
        seen_ids = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {"id", "reason"}:
                raise RetrieverError(f"{group} 的每项必须仅含 id 和 reason")
            entry_id = item["id"]
            reason = item["reason"]
            if not isinstance(entry_id, str) or entry_id not in allowed_ids:
                raise RetrieverError(f"{group} 选择了不属于该组目录的 ID")
            if entry_id in seen_ids:
                raise RetrieverError(f"{group} 重复选择了 {entry_id}")
            if not isinstance(reason, str) or not reason.strip():
                raise RetrieverError(f"{entry_id} 的 reason 必须是非空字符串")
            seen_ids.add(entry_id)
            selected_ids.append(entry_id)
    return selection, selected_ids


def select_initial_candidates(
    snapshot: RetrievalSnapshot,
    problem_analysis: dict[str, Any],
    *,
    snapshot_events: Sequence[dict[str, Any]],
    model_call: Callable[[str], str],
    record: Callable[[dict[str, Any]], None],
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """初选一轮。向全文阶段交接时传入与模型调用绑定的配置。"""
    version: dict[str, str] = {}
    operation = "retriever_initial_selection"
    stage = "catalog"
    metadata = {}
    try:
        if model_config is not None:
            metadata["model_config"] = _model_config(model_config)
        start = len(snapshot_events)
        catalog = snapshot.catalog()
        version = _catalog_version(snapshot_events[start:])

        stage = "request"
        request = _build_request(problem_analysis, catalog)
        record({"operation": operation, "stage": stage, "status": "ok", **version, **deepcopy(metadata),
                "request": request})

        stage = "model_call"
        response = _call_model(model_call, request)

        stage = "response"
        record({"operation": operation, "stage": stage, "status": "ok", **version, **deepcopy(metadata),
                "response": response})
        stage = "selection"
        selection, selected_ids = _parse_selection(response, catalog)
    except (LibraryError, RetrieverError) as exc:
        record({"operation": operation, "stage": stage, "status": "error", **version, "reason": str(exc)})
        if isinstance(exc, LibraryError):
            raise RetrieverError(str(exc)) from exc
        raise

    result = {"selection": selection, "selected_ids": selected_ids, **version, **metadata}
    event = {"operation": operation, "stage": stage, "status": "ok", **deepcopy(result)}
    if not selected_ids:
        event["message"] = "本轮未选中材料"
    record(event)
    return result
