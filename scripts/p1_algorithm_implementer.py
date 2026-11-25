"""按已接受的设计稿生成待评价的 Python 求解器。"""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any

from .p1_library_reader import ID_PATTERN
from .p1_problem_analyzer import ProblemAnalysisError, _nonblank, _text_array, _validate_contract
from .p1_retriever import RetrieverError, _call_model, _decode_response, _encode_request, _model_config


ALGORITHM_IMPLEMENTATION_PROMPT = """\
You are the algorithm implementer. Follow the accepted design and solver
interface. Preserve the authoritative objective and feasible region, component
semantics, data and control flow, and the shared deadline. You may choose coding
details and improve efficiency without changing the algorithm or its interfaces.
Use the supplied versions of any required materials.

For a successful implementation, return one JSON object with exactly
design_version, code and implementation_notes. Copy design_version verbatim.
Write the complete Python source as a string in code, including any helpers.
Define a plain top-level function solve(instance, seed, time_limit) and follow
the supplied time unit and solution format. In implementation_notes explain
how the code implements the design. Do not claim to have run or evaluated it.

If a missing interface, contradictory step or required algorithm change makes
faithful implementation impossible, return exactly design_version and
design_gap, without code. The design_gap object must contain location,
design_quote, basis, impact and needed_decision. Location is a nonempty array
of field names and zero-based list indices pointing to text in design.
Quote that text exactly in design_quote. In basis name the original constraint,
solver interface or component requirement that conflicts. Explain the
consequence and what the designer needs to decide. Do not invent a silent fix.
Return only JSON without duplicate keys."""

_ENTRY_ARGS = ("instance", "seed", "time_limit")
_GAP_TEXT = ("design_quote", "basis", "impact", "needed_decision")


class AlgorithmImplementationError(RuntimeError):
    """本次实现响应无法交接。"""


def _check_design(
    design: dict[str, Any], contract: dict[str, Any], interface: dict[str, Any],
) -> set[str]:
    fields = ("instance", "seed", "time_limit", "solution")
    if not isinstance(interface, dict) or not all(_nonblank(interface.get(field)) for field in fields):
        raise AlgorithmImplementationError("受控求解接口须说明 instance、seed、time_limit 和 solution")
    if not isinstance(design, dict) or design.get("solver_interface") != interface:
        raise AlgorithmImplementationError("受控求解接口与已接受设计稿不一致")
    feasibility = design.get("feasibility")
    constraints = feasibility.get("hard_constraints") if isinstance(feasibility, dict) else None
    if (not isinstance(constraints, list) or any(not isinstance(item, dict) for item in constraints)
            or [item.get("constraint") for item in constraints] != contract["constraints"]
            or feasibility.get("objective") != contract["objective"]):
        raise AlgorithmImplementationError("已接受设计稿的目标或硬约束与原问题合同不一致")

    components = design.get("components")
    if not isinstance(components, list) or not components:
        raise AlgorithmImplementationError("已接受设计稿缺少 components")
    required = set()
    for component in components:
        if not isinstance(component, dict) or not _text_array(component.get("material_ids")):
            raise AlgorithmImplementationError("设计组件缺少有效的 material_ids")
        required.update(component["material_ids"])
    return required


def _select_materials(
    materials: Sequence[dict[str, Any]], required: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(materials, Sequence) or isinstance(materials, (str, bytes)):
        raise AlgorithmImplementationError("materials 必须是检索材料序列")
    provided = {}
    for material in materials:
        entry = material.get("entry") if isinstance(material, dict) else None
        if not isinstance(entry, dict):
            raise AlgorithmImplementationError("检索材料缺少 entry")
        entry_id = entry.get("algorithm_id", entry.get("case_id"))
        if not isinstance(entry_id, str) or not ID_PATTERN.fullmatch(entry_id) or entry_id in provided:
            raise AlgorithmImplementationError("检索材料的条目 ID 无效或重复")
        provided[entry_id] = material
    missing = required - provided.keys()
    if missing:
        raise AlgorithmImplementationError("缺少设计所需材料：" + "、".join(sorted(missing)))
    return [item for entry_id, item in provided.items() if entry_id in required]


def _check_source(code: str) -> None:
    try:
        tree = ast.parse(code, filename="<solver>")
        compile(tree, "<solver>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        raise AlgorithmImplementationError(f"Python 源码语法不合格（第 {exc.lineno} 行）：{exc.msg}") from exc
    except (ValueError, RecursionError) as exc:
        raise AlgorithmImplementationError(f"Python 源码无法静态检查（{type(exc).__name__}）") from exc

    entries = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == "solve"]
    if len(entries) == 1 and isinstance(entries[0], ast.FunctionDef):
        entry = entries[0]
        args = entry.args
        if (tuple(arg.arg for arg in args.args) == _ENTRY_ARGS and not entry.decorator_list
                and not (args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults)):
            return
    raise AlgorithmImplementationError("源码须定义唯一的顶层普通入口 solve(instance, seed, time_limit)")


def _check_gap(value: Any, design: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != {"location", *_GAP_TEXT}
            or not all(_nonblank(value[field]) for field in _GAP_TEXT)):
        raise AlgorithmImplementationError("方案缺口须包含位置、设计引文、冲突依据、影响和所需决定")
    path = value["location"]
    if not isinstance(path, list) or not path:
        raise AlgorithmImplementationError("方案缺口 location 必须是非空的设计字段路径")
    location: Any = design
    for key in path:
        if isinstance(location, dict) and isinstance(key, str) and key in location:
            location = location[key]
        elif isinstance(location, list) and type(key) is int and 0 <= key < len(location):
            location = location[key]
        else:
            raise AlgorithmImplementationError("方案缺口 location 无法定位到当前设计稿")
    if not isinstance(location, str) or value["design_quote"] not in location:
        raise AlgorithmImplementationError("方案缺口 design_quote 不在所指的当前设计内容中")
    return value


def _parse_implementation(response: str, design: dict[str, Any], design_version: str) -> dict[str, Any]:
    value = _decode_response(response)
    if not isinstance(value, dict) or value.get("design_version") != design_version:
        raise AlgorithmImplementationError("实现响应须为 JSON 对象并沿用已接受的 design_version")
    if set(value) == {"design_version", "design_gap"}:
        gap = _check_gap(value["design_gap"], design)
        return {"status": "design_gap", "design_version": design_version, "design_gap": gap}
    if (set(value) != {"design_version", "code", "implementation_notes"}
            or not _nonblank(value["code"]) or not _nonblank(value["implementation_notes"])):
        raise AlgorithmImplementationError("成功响应须包含非空 code、implementation_notes 和 design_version")
    _check_source(value["code"])
    return {"status": "pending_evaluation", **value}


def implement_algorithm(
    problem_contract: dict[str, Any],
    design: dict[str, Any],
    solver_interface: dict[str, Any],
    *,
    design_version: str,
    model_config: dict[str, Any],
    model_call: Callable[[str, dict[str, Any]], str],
    record: Callable[[dict[str, Any]], None],
    materials: Sequence[dict[str, Any]] = (),
    experience: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """返回待评价源码或有定位依据的方案缺口。源码只作内存静态检查。"""
    stage = "input"
    metadata: dict[str, Any] = {}

    def emit(status: str, **details: Any) -> None:
        record({"operation": "algorithm_implementation", "stage": stage, "status": status,
                **deepcopy(metadata), **deepcopy(details)})

    try:
        config = _model_config(model_config)
        metadata["model_config"] = config
        if not _nonblank(design_version):
            raise AlgorithmImplementationError("design_version 必须是非空字符串")
        metadata["design_version"] = design_version
        contract = deepcopy(problem_contract)
        _validate_contract(contract)
        accepted = deepcopy(design)
        interface = deepcopy(solver_interface)
        required = _check_design(accepted, contract, interface)
        supplied = _select_materials(materials, required)
        stage = "request"
        request = _encode_request(ALGORITHM_IMPLEMENTATION_PROMPT, {
            "problem_contract": contract, "design": accepted, "solver_interface": interface,
            "design_version": design_version, "materials": supplied, "experience": experience,
        }, "算法实现输入")
        emit("ok", request=request)
        stage = "model_call"
        response = _call_model(lambda sent: model_call(sent, deepcopy(config)), request)
        stage = "response"
        emit("ok", response=response)
        stage = "implementation"
        result = _parse_implementation(response, accepted, design_version)
    except (AlgorithmImplementationError, ProblemAnalysisError, RetrieverError) as exc:
        emit("error", reason=str(exc))
        if isinstance(exc, AlgorithmImplementationError):
            raise
        raise AlgorithmImplementationError(str(exc)) from exc

    emit(result["status"], result=result)
    return result
