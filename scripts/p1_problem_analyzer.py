"""生成并校验初始化阶段交给 Retriever 的问题分析。"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from .p1_retriever import RetrieverError, _call_model, _decode_response, _encode_request, _model_config


PROBLEM_ANALYSIS_PROMPT = """\
You are the problem analyst in the initialization phase of hybrid algorithm design.
Use problem_contract and the supplied design_instance or instance_format.
Describe the decisions, representations, coupling and decomposition opportunities.
Identify where distinct optimization components might interact, and state concrete
design needs the Retriever can look up. Do not choose library entry IDs or
invent instance properties, evaluation results or performance claims.

Treat problem_contract as authoritative. Keep the original objective and feasible
region. Separate hard constraints from restrictions of possible algorithms or
representations. Put assumptions that still need checking in hypotheses.

Return one JSON object with exactly problem, objective, constraints,
problem_structure, design_needs and hypotheses. Copy problem, objective and
constraints from problem_contract verbatim, keeping the order of constraints.
Write problem_structure as nonblank text and design_needs as a nonempty array of
nonblank strings. Write hypotheses as an array of nonblank strings, or [] if empty.
If a missing or conflicting fact prevents reliable analysis, return only
problem_gaps, a nonempty array of nonblank strings that identify the issues.
Return only JSON without Markdown or duplicate keys."""

_CONTRACT_FIELDS = ("problem", "objective", "constraints")
_ANALYSIS_FIELDS = {*_CONTRACT_FIELDS, "problem_structure", "design_needs", "hypotheses"}


class ProblemAnalysisError(RuntimeError):
    """问题没能完成分析，当前结果无法交接。"""


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_array(value: Any) -> bool:
    return isinstance(value, list) and all(_nonblank(item) for item in value)


def _validate_contract(contract: dict[str, Any]) -> None:
    if not isinstance(contract, dict):
        raise ProblemAnalysisError("原问题合同必须是 JSON 对象")
    for field in ("problem", "objective"):
        if not _nonblank(contract.get(field)):
            raise ProblemAnalysisError(f"原问题合同的 {field} 必须是非空字符串")
    if not _text_array(contract.get("constraints")):
        raise ProblemAnalysisError("原问题合同的 constraints 必须是非空字符串的数组")


def _parse_analysis(response: str, contract: dict[str, Any]) -> dict[str, Any]:
    value = _decode_response(response)
    if not isinstance(value, dict):
        raise ProblemAnalysisError("问题分析响应必须是 JSON 对象")
    if set(value) == {"problem_gaps"}:
        gaps = value["problem_gaps"]
        if not _text_array(gaps) or not gaps:
            raise ProblemAnalysisError("problem_gaps 必须是包含至少一项的非空字符串数组")
        raise ProblemAnalysisError("原问题信息缺失或冲突：" + "；".join(gaps))

    missing = sorted(_ANALYSIS_FIELDS - value.keys())
    unexpected = sorted(value.keys() - _ANALYSIS_FIELDS)
    if missing or unexpected:
        raise ProblemAnalysisError(f"问题分析响应字段不符，缺少 {missing}，额外 {unexpected}")

    differences = [
        f"{field} 原值 {contract[field]!r}，响应值 {value[field]!r}"
        for field in _CONTRACT_FIELDS
        if value[field] != contract[field]
    ]
    if differences:
        raise ProblemAnalysisError("问题分析响应与原问题合同不一致：" + "；".join(differences))
    if not _nonblank(value["problem_structure"]):
        raise ProblemAnalysisError("problem_structure 必须是非空字符串")
    if not _text_array(value["design_needs"]) or not value["design_needs"]:
        raise ProblemAnalysisError("design_needs 必须是包含至少一项的非空字符串数组")
    if not _text_array(value["hypotheses"]):
        raise ProblemAnalysisError("hypotheses 必须是非空字符串的数组")

    return {**value, **{field: contract[field] for field in _CONTRACT_FIELDS}}


def analyze_problem(
    problem_contract: dict[str, Any],
    *,
    model_config: dict[str, Any],
    model_call: Callable[[str, dict[str, Any]], str],
    record: Callable[[dict[str, Any]], None],
    design_instance: Any = None,
    instance_format: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用一次问题分析者，返回可原样传给 Retriever 的 problem_analysis。

    调用器接收完整请求和实际应使用的模型配置。至少提供设计实例或实例格式。
    合同、调用或响应校验失败时记录原因并抛出 ProblemAnalysisError。
    """
    stage = "input"
    metadata: dict[str, Any] = {}

    def emit(status: str, **details: Any) -> None:
        record({"operation": "problem_analysis", "stage": stage, "status": status,
                **deepcopy(metadata), **deepcopy(details)})

    try:
        config = _model_config(model_config)
        metadata["model_config"] = config
        _validate_contract(problem_contract)
        if instance_format is not None and not (
            _nonblank(instance_format) or (isinstance(instance_format, dict) and instance_format)
        ):
            raise ProblemAnalysisError("instance_format 必须是非空字符串或非空 JSON 对象")
        if design_instance is None and instance_format is None:
            raise ProblemAnalysisError("至少提供 design_instance 或 instance_format")

        stage = "request"
        contract = deepcopy(problem_contract)
        request = _encode_request(PROBLEM_ANALYSIS_PROMPT, {
            "problem_contract": contract,
            "design_instance": design_instance,
            "instance_format": instance_format,
        }, "原问题合同或实例信息")
        emit("ok", request=request)

        stage = "model_call"
        response = _call_model(lambda sent: model_call(sent, deepcopy(config)), request)
        stage = "response"
        emit("ok", response=response)

        stage = "analysis"
        analysis = _parse_analysis(response, contract)
    except (RetrieverError, ProblemAnalysisError) as exc:
        emit("error", reason=str(exc))
        if isinstance(exc, RetrieverError):
            raise ProblemAnalysisError(str(exc)) from exc
        raise

    emit("ok", problem_analysis=analysis)
    return analysis
