"""受控验收混合方案设计者和 Retriever 交接。"""

import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from scripts.p1_full_retrieval import FULL_RETRIEVAL_PROMPT, retrieve_full_materials
from scripts.p1_hybrid_designer import HYBRID_DESIGN_PROMPT, HybridDesignBlocked, HybridDesignError, design_hybrid
from scripts.p1_library_reader import RetrievalSnapshot
from scripts.p1_retriever import select_initial_candidates


CONFIG = {"model": "fixture", "version": "1", "temperature": 0}
PROBLEM = {
    "problem": "CVRP",
    "objective": "最小化未取整的欧氏路线总距离",
    "constraints": ["单仓库", "容量可行", "每客户恰好服务一次", "车辆数可变"],
}
ANALYSIS = {**PROBLEM, "problem_structure": "分配客户并排序",
            "design_needs": ["路线解码与改进"], "hypotheses": []}
INTERFACE = {
    "instance": "仓库坐标、客户坐标、需求和车辆容量",
    "seed": "非负整数", "time_limit": "墙钟毫秒",
    "solution": "客户编号路线数组，仓库由接口隐含",
}
VERSION = {"snapshot_id": "fixture", "manifest_sha256": "e" * 64}
SELECTION = {"algorithms": [], "cases": [{"id": "CASE-001", "reason": "查阅解码和局部改进的衔接"}]}
INITIAL = {"selection": SELECTION, "selected_ids": ["CASE-001"], "model_config": CONFIG, **VERSION}
CASE_QUOTE = "Split converts each permutation into routes; local search improves them"
CASE = {
    "entry": {"case_id": "CASE-001", "description": CASE_QUOTE, "code": "fixture source"},
    "json_file": {"path": "cases/CASE-001/CASE-001.json", "sha256": "a" * 64},
    "source": {"path": "cases/CASE-001/CASE-001.md", "sha256": "b" * 64, "content": "fixture note"},
}
VERSIONS = {CASE[key]["path"]: CASE[key]["sha256"] for key in ("json_file", "source")}
CITATION = {"id": "CASE-001", "field": "description", "quote": CASE_QUOTE, "line": 1}
FINDINGS = [
    {"claim": CASE_QUOTE, "kind": "source", "citations": [CITATION]},
    {"claim": "解码后进行局部改进", "kind": "paraphrase", "citations": [CITATION]},
    {"claim": "若解码保证容量可行，可能迁移到可变车数设定", "kind": "inference", "citations": [CITATION]},
    {"claim": "现有解码器支持无条件可变车数", "kind": "unverified", "citations": []},
]
FULL = {
    "status": "ok", "findings": FINDINGS, "gaps": ["现有解码器的可变车数支持未证实"],
    "file_versions": VERSIONS, "loaded_ids": ["CASE-001"], "model_config": CONFIG, **VERSION,
}
DESIGN = {
    "summary": "构造容量可行路线，将完整路线交给局部搜索改进。",
    "representation": {"instance": "坐标和需求数组", "solution": "若干客户编号路线",
                       "conversions": "按排列逐个插入，容量不足时开始新路线"},
    "components": [
        {"id": "construct", "origin": "new", "purpose": "创建容量可行路线", "inputs": "客户排列",
         "outputs": "完整路线", "conditions": "每个客户需求小于或等于总容量", "operators": "顺序插入",
         "parameter_policy": "用原容量", "material_ids": []},
        {"id": "improve", "origin": "adapted", "purpose": "缩短总距离", "inputs": "容量可行路线",
         "outputs": "容量可行路线", "conditions": "仅接受可行移动", "operators": "路线内 2-opt",
         "parameter_policy": "只接受严格改进", "material_ids": ["CASE-001"]},
    ],
    "connections": [{"from": "construct", "to": "improve", "data": "完整路线", "trigger": "构造结束"}],
    "state": "维护当前最佳完整路线",
    "feasibility": {
        "objective": PROBLEM["objective"],
        "objective_computation": "按原始坐标计算闭路线总长度",
        "local_boundaries": "局部搜索保留路线归属和容量状态",
        "hard_constraints": [
            {"constraint": constraint, "handling": handling}
            for constraint, handling in zip(PROBLEM["constraints"], [
                "所有路线从同一仓库出发并回到该仓库", "插入前累加需求检查容量",
                "构造只遍历每位客户一次，搜索只重排", "按需增加路线",
            ], strict=True)
        ],
    },
    "execution": {"shared_deadline": "构造与搜索共用墙钟截止时间", "termination": "到限或无改进",
                  "early_exit": "按接口返回已构造并验过的最佳完整路线数组"},
    "evidence_use": [
        {"finding_index": 0, "use": "supporting", "conditions": "参考连接顺序"},
        {"finding_index": 1, "use": "supporting", "conditions": "只保留解码后改进的衔接"},
        {"finding_index": 2, "use": "hypothesis", "conditions": "解码具备容量可行性时"},
        {"finding_index": 3, "use": "hypothesis", "conditions": "仅待验证，当前使用新构造器"},
    ],
    "performance_hypotheses": ["局部改进可能降低总距离，等待评价"],
}


def request_payload(request):
    return json.loads(request.split("\n\nInput JSON\n", 1)[1])


def sent_request(**changes):
    return FULL_RETRIEVAL_PROMPT + "\n\nInput JSON\n" + json.dumps({
        "problem_analysis": ANALYSIS, "materials": [CASE], "file_versions": VERSIONS, **changes,
    })


class HybridDesignerTest(unittest.TestCase):
    def setUp(self):
        self.events = []

    def run_designer(self, model, **overrides):
        options = {
            "problem_contract": PROBLEM, "problem_analysis": ANALYSIS, "solver_interface": INTERFACE,
            "initial_selection": INITIAL, "full_retrieval": FULL, "full_request": sent_request(),
            "model_config": CONFIG, "record": self.events.append, **overrides,
        }
        return design_hybrid(model_call=model, **options)

    def test_preserves_handoff_and_evidence_without_evaluation_or_experience(self):
        raw = json.dumps(DESIGN, ensure_ascii=False)
        model = Mock(return_value=raw)
        design = self.run_designer(model)
        model.assert_called_once()
        request, config = model.call_args.args
        self.assertTrue(request.startswith(HYBRID_DESIGN_PROMPT))
        self.assertEqual(config, CONFIG)
        self.assertEqual(request_payload(request), {
            "problem_contract": PROBLEM, "problem_analysis": ANALYSIS, "solver_interface": INTERFACE,
            "initial_selection": INITIAL, "full_retrieval": FULL, "materials": [CASE],
            "evaluation": None, "experience": None,
        })
        self.assertEqual(design["solver_interface"], INTERFACE)
        self.assertEqual([ref["finding"] for ref in design["evidence_use"]], FINDINGS)
        self.assertEqual(design["evidence_use"][2]["conditions"], "解码具备容量可行性时")
        self.assertEqual([event["stage"] for event in self.events], ["request", "response", "design"])
        self.assertEqual(self.events[0]["request"], request)
        self.assertEqual(self.events[1]["response"], raw)
        self.assertTrue(all(event["model_config"] == CONFIG and event["snapshot_id"] == VERSION["snapshot_id"]
                            for event in self.events))
        design["evidence_use"][0]["finding"]["kind"] = "unverified"
        self.assertEqual(self.events[-1]["design"]["evidence_use"][0]["finding"], FINDINGS[0])

    def test_rejects_incomplete_or_inconsistent_design_before_handoff(self):
        cases = [
            (("representation", "conversions"), "representation.*conversions"),
            (("components", 0, "outputs"), "组件.*outputs"),
            (("feasibility", "hard_constraints", 1, "handling"), "硬约束.*handling"),
            (("execution", "early_exit"), "execution.*early_exit"),
            (("feasibility", "hard_constraints", 1), "与原问题合同不一致"),
        ]
        for path, error in cases:
            with self.subTest(path=path):
                draft = deepcopy(DESIGN)
                target = draft
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]
                raw = json.dumps(draft)
                with self.assertRaisesRegex(HybridDesignError, error):
                    self.run_designer(Mock(return_value=raw))
                self.assertEqual(self.events[-2]["response"], raw)
                self.assertEqual(self.events[-1]["status"], "error")
                self.assertNotIn("design", self.events[-1])

    def test_rejects_bad_connections_and_unsupplied_material_references(self):
        draft = deepcopy(DESIGN)
        draft["connections"][0]["to"] = "missing"
        with self.assertRaisesRegex(HybridDesignError, "已定义的不同组件"):
            self.run_designer(Mock(return_value=json.dumps(draft)))
        with self.assertRaisesRegex(HybridDesignError, "未交付的实收材料"):
            self.run_designer(Mock(return_value=json.dumps(DESIGN)), full_request=None)

    def test_can_design_without_full_material_if_the_design_does_not_depend_on_it(self):
        draft = deepcopy(DESIGN)
        draft["components"][1]["material_ids"] = []
        model = Mock(return_value=json.dumps(draft))
        design = self.run_designer(model, full_request=None)
        self.assertEqual(request_payload(model.call_args.args[0])["materials"], [])
        self.assertEqual(design["evidence_use"][-1]["finding"]["kind"], "unverified")

    def test_unverified_or_inferred_findings_cannot_be_established_premises(self):
        for index, kind, use in ((2, "inference", "required"), (3, "unverified", "required"),
                                 (3, "unverified", "supporting")):
            with self.subTest(kind=kind, use=use):
                draft = deepcopy(DESIGN)
                draft["evidence_use"][index]["use"] = use
                with self.assertRaisesRegex(HybridDesignError, f"{kind}.*{use}"):
                    self.run_designer(Mock(return_value=json.dumps(draft)))
                self.assertNotIn("design", self.events[-1])

    def test_reports_blocking_gaps_separately_from_call_failure(self):
        gap = "现有解码器能否处理可变车数尚未核实"
        with self.assertRaises(HybridDesignBlocked) as exc:
            self.run_designer(Mock(return_value=json.dumps({"blocking_gaps": [gap]})))
        self.assertEqual(exc.exception.gaps, (gap,))
        self.assertEqual(self.events[-1]["status"], "blocked")
        self.assertEqual(self.events[-1]["blocking_gaps"], [gap])
        analyst = Mock(side_effect=TimeoutError("fixture"))
        with self.assertRaisesRegex(HybridDesignError, "TimeoutError"):
            self.run_designer(analyst)
        self.assertEqual(self.events[-2]["request"], analyst.call_args.args[0])
        self.assertEqual(self.events[-1]["status"], "error")

    def test_inconsistent_or_stopped_retrieval_does_not_call_designer(self):
        invalid = [
            ({"full_retrieval": {**FULL, "status": "stopped"}}, "状态为 ok"),
            ({"full_retrieval": {**FULL, "snapshot_id": "other"}}, "快照不一致"),
            ({"full_request": sent_request(materials=[])}, "loaded_ids 不一致"),
            ({"full_request": sent_request(file_versions={})}, "文件版本与交接不一致"),
            ({"full_request": sent_request(problem_analysis={})}, "问题分析或文件版本"),
        ]
        for options, error in invalid:
            with self.subTest(error=error):
                designer = Mock()
                with self.assertRaisesRegex(HybridDesignError, error):
                    self.run_designer(designer, **options)
                designer.assert_not_called()
                self.assertEqual(self.events[-1]["stage"], "input")

    def test_accepts_real_retriever_output_with_mock_models_and_formal_snapshot(self):
        events, logs = [], []
        snapshot = RetrievalSnapshot(record=events.append)
        initial = select_initial_candidates(
            snapshot, ANALYSIS, snapshot_events=events, model_config=CONFIG,
            model_call=lambda _: json.dumps(SELECTION), record=logs.append,
        )
        full_model = Mock(return_value=json.dumps({
            "findings": [{**FINDINGS[0], "citations": [{k: v for k, v in CITATION.items() if k != "line"}]}],
            "supplement_ids": [], "gaps": [],
        }))
        full = retrieve_full_materials(
            snapshot, initial, ANALYSIS, snapshot_events=events, model_config=CONFIG,
            model_call=full_model, check_support=lambda *_: True, check_budget=lambda _: True,
            record=logs.append,
        )
        raw_design = {**DESIGN, "evidence_use": DESIGN["evidence_use"][:1]}
        designer = Mock(return_value=json.dumps(raw_design))
        sent = full_model.call_args.args[0]
        design = self.run_designer(designer, initial_selection=initial, full_retrieval=full, full_request=sent)
        self.assertEqual(design["evidence_use"][0]["finding"], full["findings"][0])
        self.assertEqual(request_payload(designer.call_args.args[0])["materials"], request_payload(sent)["materials"])


if __name__ == "__main__":
    unittest.main()
