"""Retriever 的全文请求、补读和证据核验。"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

from .p1_library_reader import ID_PATTERN, LibraryError, RetrievalSnapshot, _validate_ids
from .p1_retriever import RetrieverError, _call_model, _decode_response, _encode_request, _model_config, _read_version


FULL_RETRIEVAL_PROMPT = """\
You are the Retriever reviewing material for hybrid algorithm design.
Use only the descriptions, code, and sources supplied in materials as
evidence. Preserve the stated objective, constraints, and design needs.

Return one JSON object with exactly findings, supplement_ids, and gaps.
Each is an array. Each finding has claim, kind, and citations. State one
concrete claim. Choose one kind: source, paraphrase, inference, or unverified.
Source claims reproduce an excerpt. Paraphrases preserve its meaning.
Inferences state a possible adaptation and its conditions. Mark unsupported
details as unverified. Mentioning another entry does not establish its
implementation. Identify entries by their IDs in your claims.

Each citation has id, field, and quote. Quote exact text from the named
entry. Use description or source for text fields, code for a case's
assembled code, or code:<path> for an actual algorithm file. Cite enough
context to support the claim. Unverified claims may omit citations.
Request specific, still-needed entries by ID in supplement_ids. In gaps,
state unresolved material or evidence needs. Return only JSON."""

_ENTRY_MENTION = re.compile(r"(?<![A-Za-z0-9_-])(?:ALG|CASE)-[0-9]{3}(?![A-Za-z0-9_-])")
_KINDS = {"source", "paraphrase", "inference", "unverified"}
SupportCheck = Callable[[str, str, list[dict[str, Any]]], bool | None]


def _field_content(material: dict[str, Any], field: str) -> str | None:
    if field == "description":
        return material["entry"]["description"]
    if field == "source":
        return material["source"]["content"]
    code = material["entry"]["code"]
    if isinstance(code, str):
        return code if field == "code" else None
    if field.startswith("code:"):
        path = field.removeprefix("code:")
        return next((item["content"] for item in code["files"] if item["path"] == path), None)
    return None


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_findings(
    response: str, materials: dict[str, dict[str, Any]], check_support: SupportCheck,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    value = _decode_response(response)
    if (not isinstance(value, dict) or set(value) != {"findings", "supplement_ids", "gaps"}
            or any(not isinstance(items, list) for items in value.values())
            or any(not _nonblank(gap) for gap in value["gaps"])):
        raise RetrieverError("全文响应须包含 findings、supplement_ids 和 gaps 三个数组，缺口须为非空文本")
    _validate_ids(value["supplement_ids"])
    findings = []
    gaps = list(value["gaps"])
    for item in value["findings"]:
        if (not isinstance(item, dict) or set(item) != {"claim", "kind", "citations"}
                or not _nonblank(item["claim"]) or not isinstance(item["kind"], str)
                or item["kind"] not in _KINDS or not isinstance(item["citations"], list)):
            raise RetrieverError("全文结论的 claim、kind 或 citations 无效")
        claim, kind = item["claim"], item["kind"]
        reasons = []
        absent = sorted(set(_ENTRY_MENTION.findall(claim)) - materials.keys())
        if absent:
            reasons.append(f"本轮未下发条目 {', '.join(absent)} 的独立材料")
        citations = []
        for citation in item["citations"]:
            if (not isinstance(citation, dict) or set(citation) != {"id", "field", "quote"}
                    or not all(_nonblank(part) for part in citation.values())):
                raise RetrieverError("引文须包含非空的 id、field 和 quote")
            entry_id, field, quote = citation["id"], citation["field"], citation["quote"]
            target = materials.get(entry_id)
            content = _field_content(target, field) if target is not None else None
            offset = content.find(quote) if content is not None else -1
            if offset < 0:
                reasons.append(f"无法从本轮材料定位引文 {entry_id} / {field}")
            else:
                citations.append({**citation, "line": content.count("\n", 0, offset) + 1})
        if kind != "unverified" and not reasons:
            if not citations:
                reasons.append("缺少可定位引文")
            elif kind == "source" and not any(claim == citation["quote"] for citation in citations):
                reasons.append("来源原文与引文不一致")
            else:
                try:
                    supported = check_support(claim, kind, deepcopy(citations))
                except Exception as exc:
                    reasons.append(f"引文支撑判定失败（{type(exc).__name__}）")
                else:
                    if supported is not True:
                        reasons.append("引文尚未确认支撑该结论")
        gaps.extend(reasons)
        findings.append({"claim": claim, "kind": "unverified" if reasons else kind, "citations": citations})
    return findings, value["supplement_ids"], gaps


def _catalog_ids(events: Sequence[dict[str, Any]], version: dict[str, Any]) -> set[str]:
    catalog = next((item for item in reversed(events) if item.get("operation") == "catalog"), {})
    files = catalog.get("files")
    if (catalog.get("status") != "ok" or not isinstance(files, dict)
            or any(catalog.get(key) != value for key, value in version.items())):
        raise RetrieverError("全文检索与初选目录的快照版本不一致或缺少目录记录")
    stems = {PurePosixPath(name).stem for name in files if name.endswith(".json")}
    return {entry_id for entry_id in stems if ID_PATTERN.fullmatch(entry_id)}


def retrieve_full_materials(
    snapshot: RetrievalSnapshot,
    initial_selection: dict[str, Any],
    problem_analysis: dict[str, Any],
    *,
    snapshot_events: Sequence[dict[str, Any]],
    model_config: dict[str, Any],
    model_call: Callable[[str], str],
    check_budget: Callable[[str], bool | None],
    check_support: SupportCheck,
    record: Callable[[dict[str, Any]], None],
    empty_selection_supplement: list[str] | None = None,
) -> dict[str, Any]:
    """在同一轮初始化中，依据实际发送的冻结材料交付核验结果。"""
    metadata = {}
    stage = "handoff"
    round_number = 0

    def emit(status, **details):
        record({"operation": "retriever_full_materials", "stage": stage, "status": status,
                "round": round_number, **deepcopy(metadata), **details})

    materials: dict[str, dict[str, Any]] = {}
    versions: dict[str, str] = {}
    findings: list[dict[str, Any]] = []
    gaps: list[str] = []
    model_gaps: list[str] = []
    try:
        config = _model_config(model_config)
        initial_config = _model_config(initial_selection.get("model_config"))
        if any(config[key] != initial_config[key] for key in ("model", "version")):
            raise RetrieverError("全文检索须沿用初选的模型底座和版本")
        version = {key: initial_selection.get(key) for key in ("snapshot_id", "manifest_sha256")}
        known = _catalog_ids(snapshot_events, version)
        metadata = {**version, "model_config": config}
        pending = initial_selection.get("selected_ids")
        _validate_ids(pending)
        if not set(pending) <= known:
            raise RetrieverError("初选 ID 与本轮目录不一致")
        if not isinstance(problem_analysis, dict):
            raise RetrieverError("问题分析必须是 JSON 对象")
        if not pending:
            gaps.append("本轮未选中材料，跳过初选全文加载")
            pending = [] if empty_selection_supplement is None else empty_selection_supplement
            _validate_ids(pending)

        while pending:
            unavailable = [entry_id for entry_id in pending if entry_id not in known]
            gaps.extend(f"补读条目 {entry_id} 不在本轮快照目录" for entry_id in unavailable)
            requested = [entry_id for entry_id in pending if entry_id in known and entry_id not in materials]
            if not requested:
                break
            round_number += 1
            stage = "load"
            start = len(snapshot_events)
            loaded = snapshot.load(requested)
            events = snapshot_events[start:]
            if _read_version(events, "load") != version:
                raise RetrieverError("实际全文材料与初选的快照版本不一致")
            read = next(event for event in events if event.get("operation") == "load")
            if read.get("ids") != requested or not isinstance(read.get("files"), dict):
                raise RetrieverError("实际全文读取事件与请求的条目不一致")
            if [PurePosixPath(item["json_file"]["path"]).stem for item in loaded] != requested:
                raise RetrieverError("实际全文条目与请求的 ID 不一致")

            stage = "budget"
            next_materials = {**materials, **dict(zip(requested, loaded, strict=True))}
            next_versions = {**versions, **read["files"]}
            request = _encode_request(FULL_RETRIEVAL_PROMPT, {
                "problem_analysis": problem_analysis,
                "materials": list(next_materials.values()),
                "file_versions": next_versions,
            }, "完整全文检索材料")
            try:
                permitted = check_budget(request)
            except Exception as exc:
                permitted = None
                reason = f"完整全文请求预算无法核验（{type(exc).__name__}）"
            else:
                reason = "完整全文请求预算不足" if permitted is False else "完整全文请求预算无法核验"
            if permitted is not True:
                gaps.append(reason)
                emit("skipped", ids=requested, reason=reason)
                break
            stage = "request"
            emit("ok", request=request, ids=list(next_materials), file_versions=next_versions.copy())
            stage = "model_call"
            response = _call_model(model_call, request)
            stage = "response"
            emit("ok", response=response)
            stage = "evidence"
            materials, versions = next_materials, next_versions
            findings, pending, model_gaps = _parse_findings(response, materials, check_support)
            emit("ok", findings=deepcopy(findings), supplement_ids=pending.copy(), gaps=model_gaps.copy())
    except (LibraryError, RetrieverError) as exc:
        emit("error", reason=str(exc))
        if isinstance(exc, LibraryError):
            raise RetrieverError(str(exc)) from exc
        raise

    status = "ok" if any(item["kind"] != "unverified" for item in findings) else "stopped"
    if status == "stopped":
        gaps.append("没有可交接的已核验结论")
    result = {"status": status, "findings": findings, "gaps": list(dict.fromkeys(gaps + model_gaps)),
              "loaded_ids": list(materials), "file_versions": versions, **metadata}
    stage = "handoff"
    emit(status, result=deepcopy(result))
    return result
