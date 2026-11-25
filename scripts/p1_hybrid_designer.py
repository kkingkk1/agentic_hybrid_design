"""设计并校验交给算法实现者的混合方案。"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

from .p1_full_retrieval import FULL_RETRIEVAL_PROMPT, _KINDS
from .p1_library_reader import HASH_PATTERN
from .p1_problem_analyzer import ProblemAnalysisError, _nonblank, _text_array, _validate_contract
from .p1_retriever import RetrieverError, _call_model, _decode_response, _encode_request, _model_config


HYBRID_DESIGN_PROMPT = """\
You are the hybrid algorithm designer. Use the authoritative problem contract,
the problem analysis and the solver interface to design one implementable solver.
Explain how distinct optimization mechanisms interact. Preserve the original
objective and feasible region. Initial selection reasons only describe relevance.
Use the final retrieval findings with their original kinds, citations and gaps.
Use only supplied materials when depending on specific library code or interfaces.
Do not claim measured benefits. Evaluation and experience may be absent.

Return one JSON object with exactly these fields:
- summary: the overall design and the role of the hybrid combination.
- representation: an object with instance, solution and conversions.
- components: at least two objects with distinct id values, origin (reused,
  adapted or new), purpose, inputs, outputs, conditions, operators,
  parameter_policy and material_ids. Use material_ids to name any supplied
  entries whose code or interfaces the component requires.
- connections: one or more objects with from, to, data and trigger. Use known
  component IDs and describe the actual handoff. The state field explains shared
  state, or how the components operate without it.
- feasibility: an object with objective (copy from problem_contract verbatim),
  objective_computation, local_boundaries and hard_constraints. For each original
  constraint in order, supply an object with constraint (copy verbatim) and handling.
- execution: an object with shared_deadline, termination and early_exit.
  In early_exit specify the complete feasible output and its format.
- evidence_use: an array of objects with finding_index (zero-based index into
  the final findings), use (required, supporting or hypothesis) and conditions.
  State the conditions of each inference. Use inference only as supporting or
  hypothesis, and unverified only as hypothesis. Required means an established
  premise essential for correctness. If a key premise is unresolved, design around
  it or return only blocking_gaps, a nonempty array of concrete unresolved issues.
- performance_hypotheses: an array of untested performance statements.

Except for the specified arrays, nested objects and finding indices, fields are
nonblank strings. material_ids, evidence_use and performance_hypotheses may be
empty.

If revision is present, review its previous_version, previous_design and
design_gap. Keep the original contract and address the identified problem using
the supplied evidence. Return a complete revised design and one additional
nonblank string field, change_summary, describing what changed and why.
Return only JSON without duplicate keys."""

_DESIGN_FIELDS = ("summary", "representation", "components", "connections", "state",
                  "feasibility", "execution", "evidence_use", "performance_hypotheses")
_COMPONENT_TEXT = ("id", "origin", "purpose", "inputs", "outputs", "conditions", "operators", "parameter_policy")


class HybridDesignError(RuntimeError):
    """混合方案无法交接。"""


class HybridDesignBlocked(HybridDesignError):
    """响应报告影响正确实现的关键缺口。"""

    def __init__(self, gaps: list[str]):
        self.gaps = tuple(gaps)
        super().__init__("设计受阻：" + "；".join(gaps))


def _object(value: Any, fields: tuple[str, ...], location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HybridDesignError(f"{location} 必须是 JSON 对象")
    missing = sorted(set(fields) - value.keys())
    extra = sorted(value.keys() - set(fields))
    if missing or extra:
        raise HybridDesignError(f"{location} 字段不符，缺少 {missing}，额外 {extra}")
    return value


def _require_text(value: dict[str, Any], fields: tuple[str, ...], location: str) -> None:
    for field in fields:
        if not _nonblank(value.get(field)):
            raise HybridDesignError(f"{location}.{field} 必须是非空字符串")


def _sent_materials(full_request, analysis, retrieval) -> tuple[list[dict[str, Any]], set[str]]:
    if full_request is None:
        return [], set()
    prefix = f"{FULL_RETRIEVAL_PROMPT}\n\nInput JSON\n"
    if not isinstance(full_request, str) or not full_request.startswith(prefix):
        raise HybridDesignError("full_request 必须是最终实发的 Retriever 全文请求")
    payload = _object(_decode_response(full_request[len(prefix):]),
                      ("problem_analysis", "materials", "file_versions"), "全文请求")
    versions = retrieval["file_versions"]
    materials = payload["materials"]
    if payload["problem_analysis"] != analysis or payload["file_versions"] != versions:
        raise HybridDesignError("全文请求的问题分析或文件版本与交接不一致")
    if not isinstance(materials, list):
        raise HybridDesignError("全文请求的 materials 必须是数组")
    ids = []
    for item in materials:
        item = _object(item, ("entry", "json_file", "source"), "全文实收材料")
        for key in ("json_file", "source"):
            info = item[key]
            if (not isinstance(info, dict) or not _nonblank(info.get("path"))
                    or info.get("sha256") != versions.get(info["path"]) or info["path"] not in versions):
                raise HybridDesignError("全文实收材料的路径或版本与交接不一致")
        entry_id = PurePosixPath(item["json_file"]["path"]).stem
        id_key = "case_id" if entry_id.startswith("CASE-") else "algorithm_id"
        if not isinstance(item["entry"], dict) or item["entry"].get(id_key) != entry_id:
            raise HybridDesignError("全文实收材料的条目 ID 与文件不一致")
        ids.append(entry_id)
    if ids != retrieval["loaded_ids"]:
        raise HybridDesignError("全文实收材料的条目与 loaded_ids 不一致")
    return materials, set(ids)


def _check_retrieval(initial: dict[str, Any], full: dict[str, Any], config: dict[str, Any]) -> None:
    if not isinstance(initial, dict) or not isinstance(initial.get("selection"), dict):
        raise HybridDesignError("初选交接缺少 selection")
    if not isinstance(full, dict) or full.get("status") != "ok":
        raise HybridDesignError("设计需要状态为 ok 的 Retriever 全文交接")
    snapshot_id, manifest = full.get("snapshot_id"), full.get("manifest_sha256")
    if (not _nonblank(snapshot_id) or not isinstance(manifest, str) or not HASH_PATTERN.fullmatch(manifest)
            or initial.get("snapshot_id") != snapshot_id or initial.get("manifest_sha256") != manifest):
        raise HybridDesignError("初选与全文交接的快照不一致或缺失")
    for retrieval in (initial, full):
        retrieved_config = _model_config(retrieval.get("model_config"))
        if any(retrieved_config[key] != config[key] for key in ("model", "version")):
            raise HybridDesignError("设计与 Retriever 须使用同一模型底座和版本")
    if (not _text_array(full.get("gaps")) or not _text_array(full.get("loaded_ids"))
            or not isinstance(full.get("file_versions"), dict)):
        raise HybridDesignError("全文交接缺少合法的 gaps、loaded_ids 或 file_versions")
    findings = full.get("findings")
    if not isinstance(findings, list) or not findings:
        raise HybridDesignError("全文交接缺少 findings")
    for item in findings:
        finding = _object(item, ("claim", "kind", "citations"), "全文结论")
        _require_text(finding, ("claim", "kind"), "全文结论")
        if finding["kind"] not in _KINDS or not isinstance(finding["citations"], list):
            raise HybridDesignError("全文结论的证据类型或引用格式无效")
    if all(finding["kind"] == "unverified" for finding in findings):
        raise HybridDesignError("全文交接没有可用的已核验结论")


def _check_components(design: dict[str, Any], material_ids: set[str]) -> None:
    components = design["components"]
    if not isinstance(components, list) or len(components) < 2:
        raise HybridDesignError("components 必须包含至少两个组件")
    component_ids = set()
    for item in components:
        component = _object(item, (*_COMPONENT_TEXT, "material_ids"), "组件")
        _require_text(component, _COMPONENT_TEXT, "组件")
        component_id = component["id"]
        if component_id in component_ids or component["origin"] not in ("reused", "adapted", "new"):
            raise HybridDesignError(f"组件 {component_id} 的 ID 重复或 origin 无效")
        if not _text_array(component["material_ids"]) or not set(component["material_ids"]) <= material_ids:
            raise HybridDesignError(f"组件 {component_id} 引用了未交付的实收材料")
        component_ids.add(component_id)

    connections = design["connections"]
    if not isinstance(connections, list) or not connections:
        raise HybridDesignError("connections 必须包含至少一条组件连接")
    for item in connections:
        fields = ("from", "to", "data", "trigger")
        connection = _object(item, fields, "组件连接")
        _require_text(connection, fields, "组件连接")
        source, target = connection["from"], connection["to"]
        if source == target or not {source, target} <= component_ids:
            raise HybridDesignError(f"组件连接 {source} → {target} 必须连接两个已定义的不同组件")


def _check_feasibility(value: Any, contract: dict[str, Any]) -> None:
    text_fields = ("objective", "objective_computation", "local_boundaries")
    feasibility = _object(value, (*text_fields, "hard_constraints"), "可行性")
    _require_text(feasibility, text_fields, "可行性")
    constraints = feasibility["hard_constraints"]
    if not isinstance(constraints, list):
        raise HybridDesignError("可行性.hard_constraints 必须是数组")
    for item in constraints:
        fields = ("constraint", "handling")
        constraint = _object(item, fields, "硬约束")
        _require_text(constraint, fields, "硬约束")
    if (feasibility["objective"] != contract["objective"]
            or [item["constraint"] for item in constraints] != contract["constraints"]):
        raise HybridDesignError("设计目标或硬约束与原问题合同不一致")


def _resolve_evidence(value: Any, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise HybridDesignError("evidence_use 必须是数组")
    resolved = []
    for item in value:
        reference = _object(item, ("finding_index", "use", "conditions"), "证据引用")
        _require_text(reference, ("use", "conditions"), "证据引用")
        index, use = reference["finding_index"], reference["use"]
        if type(index) is not int or not 0 <= index < len(findings):
            raise HybridDesignError("证据引用的 finding_index 超出最终结论范围")
        if use not in ("required", "supporting", "hypothesis"):
            raise HybridDesignError("证据引用的 use 无效")
        finding = findings[index]
        kind = finding["kind"]
        if (kind == "unverified" and use != "hypothesis") or (kind == "inference" and use == "required"):
            raise HybridDesignError(f"证据 {index} 的类别 {kind} 不能用于 {use}")
        resolved.append({**reference, "finding": deepcopy(finding)})
    return resolved


def _parse_design(response, contract, findings, material_ids, revision=None) -> dict[str, Any]:
    value = _decode_response(response)
    if isinstance(value, dict) and set(value) == {"blocking_gaps"}:
        gaps = value["blocking_gaps"]
        if not _text_array(gaps) or not gaps:
            raise HybridDesignError("blocking_gaps 必须是包含至少一项的非空字符串数组")
        raise HybridDesignBlocked(gaps)
    fields = _DESIGN_FIELDS if revision is None else (*_DESIGN_FIELDS, "change_summary")
    design = _object(value, fields, "设计稿")
    _require_text(design, ("summary", "state"), "设计稿")
    for key, fields in (("representation", ("instance", "solution", "conversions")),
                        ("execution", ("shared_deadline", "termination", "early_exit"))):
        _require_text(_object(design[key], fields, key), fields, key)
    _check_components(design, material_ids)
    _check_feasibility(design["feasibility"], contract)
    if not _text_array(design["performance_hypotheses"]):
        raise HybridDesignError("performance_hypotheses 必须是非空字符串的数组")
    design["evidence_use"] = _resolve_evidence(design["evidence_use"], findings)
    if revision is not None:
        _require_text(design, ("change_summary",), "修订稿")
        substantive = ("representation", "components", "connections", "state", "feasibility", "execution")
        if all(design[key] == revision["previous_design"].get(key) for key in substantive):
            raise HybridDesignError("修订稿未改变设计机制、接口或运行规则")
    return design


def design_hybrid(
    problem_contract: dict[str, Any],
    problem_analysis: dict[str, Any],
    solver_interface: dict[str, Any],
    initial_selection: dict[str, Any],
    full_retrieval: dict[str, Any],
    *,
    model_config: dict[str, Any],
    model_call: Callable[[str, dict[str, Any]], str],
    record: Callable[[dict[str, Any]], None],
    full_request: str | None = None,
    evaluation: dict[str, Any] | None = None,
    experience: list[dict[str, Any]] | None = None,
    revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回可交接的结构化设计。full_request 提供最终实发的全文材料。

    修订时提供旧版本、旧设计和定位缺口，返回完整设计及 change_summary。
    关键前提不足时抛出 HybridDesignBlocked，格式或合同错误抛出 HybridDesignError。
    """
    stage = "input"
    metadata: dict[str, Any] = {}

    def emit(status: str, **details: Any) -> None:
        record({"operation": "hybrid_design", "stage": stage, "status": status,
                **deepcopy(metadata), **deepcopy(details)})

    try:
        config = _model_config(model_config)
        metadata["model_config"] = config
        contract = deepcopy(problem_contract)
        _validate_contract(contract)
        analysis = deepcopy(problem_analysis)
        interface = deepcopy(solver_interface)
        if not isinstance(analysis, dict) or any(
            analysis.get(key) != contract[key] for key in ("problem", "objective", "constraints")
        ):
            raise HybridDesignError("问题分析与原问题合同不一致")
        if not isinstance(interface, dict):
            raise HybridDesignError("受控求解接口必须是 JSON 对象")
        _require_text(interface, ("instance", "seed", "time_limit", "solution"), "受控求解接口")
        full = deepcopy(full_retrieval)
        _check_retrieval(initial_selection, full, config)
        for key in ("snapshot_id", "manifest_sha256"):
            metadata[key] = full[key]
        materials, material_ids = _sent_materials(full_request, analysis, full)
        if revision is not None:
            revision = _object(deepcopy(revision), ("previous_version", "previous_design", "design_gap"), "修订输入")
            _require_text(revision, ("previous_version",), "修订输入")
            if (not isinstance(revision["previous_design"], dict)
                    or revision["previous_design"].get("solver_interface") != interface
                    or not isinstance(revision["design_gap"], dict) or not revision["design_gap"]):
                raise HybridDesignError("修订输入须包含相同求解接口的旧设计和已定位的缺口")

        stage = "request"
        payload = {
            "problem_contract": contract, "problem_analysis": analysis, "solver_interface": interface,
            "initial_selection": initial_selection, "full_retrieval": full, "materials": materials,
            "evaluation": evaluation, "experience": experience,
        }
        if revision is not None:
            payload["revision"] = revision
        request = _encode_request(HYBRID_DESIGN_PROMPT, payload, "混合设计输入")
        emit("ok", request=request)
        stage = "model_call"
        response = _call_model(lambda sent: model_call(sent, deepcopy(config)), request)
        stage = "response"
        emit("ok", response=response)
        stage = "design"
        design = _parse_design(response, contract, full["findings"], material_ids, revision)
        design["solver_interface"] = interface
    except HybridDesignBlocked as exc:
        emit("blocked", reason=str(exc), blocking_gaps=list(exc.gaps))
        raise
    except (HybridDesignError, ProblemAnalysisError, RetrieverError) as exc:
        emit("error", reason=str(exc))
        if isinstance(exc, HybridDesignError):
            raise
        raise HybridDesignError(str(exc)) from exc

    emit("ok", design=design)
    return design
