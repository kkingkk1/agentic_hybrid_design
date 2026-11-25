"""串联 P1 初始化角色并处理有限的方案缺口回交。"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from .p1_algorithm_implementer import AlgorithmImplementationError, implement_algorithm
from .p1_full_retrieval import SupportCheck, retrieve_full_materials
from .p1_hybrid_designer import HybridDesignError, _sent_materials, design_hybrid
from .p1_library_reader import FORMAL_MANIFEST, FORMAL_ROOT, LibraryError, RetrievalSnapshot
from .p1_problem_analyzer import ProblemAnalysisError, _nonblank, analyze_problem
from .p1_retriever import RetrieverError, _model_config, select_initial_candidates


_ROLE_FOR_STAGE = {
    "problem_analysis": "problem_analysis",
    "retriever_initial_selection": "retriever",
    "retriever_full_materials": "retriever",
    "hybrid_design": "hybrid_design",
    "algorithm_implementation": "algorithm_implementation",
}


class _InitializationError(RuntimeError):
    """初始化配置或预算拒绝继续执行。"""


def _initialization_configs(model_configs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    roles = set(_ROLE_FOR_STAGE.values())
    if not isinstance(model_configs, dict) or model_configs.keys() != roles:
        raise _InitializationError("model_configs 须覆盖四个初始化角色")
    configs = {role: _model_config(config) for role, config in model_configs.items()}
    if len({(config["model"], config["version"]) for config in configs.values()}) != 1:
        raise _InitializationError("初始化角色须使用同一模型底座和版本")
    return configs


def run_initialization(
    problem_contract: dict[str, Any],
    solver_interface: dict[str, Any],
    *,
    initialization_id: str,
    model_configs: dict[str, dict[str, Any]],
    model_call: Callable[[str, str, dict[str, Any]], str],
    check_budget: Callable[[str], bool | None],
    check_support: SupportCheck,
    max_revisions: int,
    design_instance: Any = None,
    instance_format: str | dict[str, Any] | None = None,
    library_root: str | Path = FORMAL_ROOT,
    manifest: str | Path = FORMAL_MANIFEST,
    record: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """交付待评价源码与设计，或返回停止原因。同步返回本轮全部记录。

    model_call 接收阶段名、实发请求和该角色的模型配置。max_revisions
    仅计初稿之后允许的方案修订，0 表示报告首个缺口后停止。
    """
    records: list[dict[str, Any]] = []
    snapshot_events: list[dict[str, Any]] = []
    configs: dict[str, dict[str, Any]] = {}
    stage = "input"
    design_version = None
    budget_stop = None
    full_request = None

    def capture(event: dict[str, Any]) -> None:
        row = {**deepcopy(event), "initialization_id": initialization_id,
               "event_index": len(records) + 1}
        role = _ROLE_FOR_STAGE.get(stage)
        if role is not None:
            row["role"] = role
            row.setdefault("model_config", deepcopy(configs[role]))
        if design_version is not None:
            row["design_version"] = design_version
        records.append(row)
        if record is not None:
            record(deepcopy(row))

    def capture_snapshot(event: dict[str, Any]) -> None:
        snapshot_events.append(deepcopy(event))
        capture(event)

    def stop(reason: str) -> dict[str, Any]:
        capture({"operation": "initialization", "stage": stage, "status": "stopped", "reason": reason})
        return {"status": "stopped", "initialization_id": initialization_id, "stage": stage,
                "reason": reason, "records": records}

    def send(request: str, config: dict[str, Any], *, prechecked: bool = False) -> str:
        nonlocal budget_stop
        request_event = records[-1]["event_index"]
        if not prechecked:
            try:
                allowed = check_budget(request)
            except Exception as exc:
                budget_stop = f"请求预算无法核验（{type(exc).__name__}）"
            else:
                if allowed is not True:
                    budget_stop = "请求预算不足" if allowed is False else "请求预算无法核验"
            if budget_stop is not None:
                capture({"operation": "initialization", "stage": "budget", "status": "skipped",
                         "request_event": request_event, "reason": budget_stop})
                raise _InitializationError(budget_stop)
        capture({"operation": "initialization", "stage": "send", "status": "attempted",
                 "request_event": request_event})
        return model_call(stage, request, deepcopy(config))

    def send_full(request: str) -> str:
        nonlocal full_request
        full_request = request
        return send(request, configs["retriever"], prechecked=True)

    try:
        if not _nonblank(initialization_id):
            raise _InitializationError("initialization_id 必须是非空字符串")
        if type(max_revisions) is not int or max_revisions < 0:
            raise _InitializationError("max_revisions 必须是非负整数")
        configs = _initialization_configs(model_configs)
        contract = deepcopy(problem_contract)
        interface = deepcopy(solver_interface)

        stage = "problem_analysis"
        analysis = analyze_problem(
            contract, design_instance=design_instance, instance_format=instance_format,
            model_config=configs["problem_analysis"], model_call=send, record=capture,
        )
        stage = "retriever_initial_selection"
        snapshot = RetrievalSnapshot(library_root, manifest=manifest, record=capture_snapshot)
        initial = select_initial_candidates(
            snapshot, analysis, snapshot_events=snapshot_events, record=capture,
            model_config=configs["retriever"], model_call=lambda request: send(request, configs["retriever"]),
        )
        stage = "retriever_full_materials"
        full = retrieve_full_materials(
            snapshot, initial, analysis, snapshot_events=snapshot_events, record=capture,
            model_config=configs["retriever"], model_call=send_full,
            check_budget=check_budget, check_support=check_support,
        )
        if full["status"] == "stopped":
            return stop("；".join(full["gaps"]))
        materials, _ = _sent_materials(full_request, analysis, full)

        revision = None
        for attempt in range(max_revisions + 1):
            stage = "hybrid_design"
            design_version = f"design-{attempt + 1}"
            design = design_hybrid(
                contract, analysis, interface, initial, full, full_request=full_request,
                model_config=configs["hybrid_design"], model_call=send, record=capture,
                revision=revision,
            )
            if revision is not None:
                capture({"operation": "initialization", "stage": "revision", "status": "accepted",
                         "previous_version": revision["previous_version"], "change_summary": design["change_summary"],
                         "design_gap": revision["design_gap"]})
            stage = "algorithm_implementation"
            implementation = implement_algorithm(
                contract, design, interface, design_version=design_version, materials=materials,
                model_config=configs["algorithm_implementation"], model_call=send, record=capture,
            )
            if implementation["status"] == "pending_evaluation":
                stage = "handoff"
                capture({"operation": "initialization", "stage": stage, "status": "pending_evaluation"})
                return {**implementation, "initialization_id": initialization_id, "design": design,
                        "problem_analysis": analysis, "initial_selection": initial, "full_retrieval": full,
                        "materials": materials, "records": records}
            if attempt == max_revisions:
                return stop(f"已达到方案修订上限（{max_revisions} 次），最新设计仍有缺口")
            revision = {"previous_version": design_version, "previous_design": design,
                        "design_gap": implementation["design_gap"]}
    except (_InitializationError, LibraryError, ProblemAnalysisError, RetrieverError,
            HybridDesignError, AlgorithmImplementationError) as exc:
        return stop(budget_stop or str(exc))
