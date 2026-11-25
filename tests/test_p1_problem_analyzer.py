"""用受控分析响应及现有 Retriever 验收任务 2.4.1。"""

import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from scripts.p1_full_retrieval import retrieve_full_materials
from scripts.p1_library_reader import RetrievalSnapshot
from scripts.p1_problem_analyzer import PROBLEM_ANALYSIS_PROMPT, ProblemAnalysisError, analyze_problem
from scripts.p1_retriever import select_initial_candidates


CONFIG = {"model": "fixture", "version": "1", "temperature": 0}
CONTRACT = {
    "problem": "CVRP",
    "objective": "最小化按未取整欧氏距离计算的总路线距离。",
    "constraints": ["单仓库", "同质车辆容量", "每位客户服务一次，需求不拆分", "使用车辆数可变"],
}
ANALYSIS = {
    **CONTRACT,
    "problem_structure": "把客户分配给路线，再确定各路线的访问顺序。",
    "design_needs": ["客户排列解码", "解码后局部改进"],
    "hypotheses": ["待验证路线解码与局部改进的衔接条件。"],
}
INSTANCE = {"capacity": 50, "depot": [0.5, 0.5], "customers": [[0.2, 0.3, 4]]}
SELECTION = {"algorithms": [], "cases": [{"id": "CASE-001", "reason": "Check decoding and local search."}]}


def payload(request):
    return json.loads(request.split("\n\nInput JSON\n", 1)[1])


class ProblemAnalyzerTest(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.snapshot_events = []
        self.snapshot = RetrievalSnapshot(record=self.snapshot_events.append)
        self.initial_model = Mock(return_value=json.dumps(SELECTION))

    def analyze(self, model, **overrides):
        options = {"model_config": CONFIG, "design_instance": INSTANCE, **overrides}
        return analyze_problem(deepcopy(CONTRACT), model_call=model, record=self.records.append, **options)

    def analyze_and_select(self, model):
        analysis = self.analyze(model)
        selection = select_initial_candidates(
            self.snapshot, analysis, snapshot_events=self.snapshot_events,
            model_call=self.initial_model, model_config=CONFIG, record=self.records.append,
        )
        return analysis, selection

    def test_handoff_reaches_existing_initial_and_full_retriever_unchanged(self):
        raw = json.dumps(ANALYSIS, ensure_ascii=False)
        analyst = Mock(return_value=raw)
        analysis, selection = self.analyze_and_select(analyst)
        request, config = analyst.call_args.args
        analyst.assert_called_once()
        self.assertEqual(config, CONFIG)
        self.assertEqual(request.split("\n\nInput JSON\n", 1)[0], PROBLEM_ANALYSIS_PROMPT)
        self.assertNotIn("CVRP", PROBLEM_ANALYSIS_PROMPT)
        self.assertEqual(payload(request), {
            "problem_contract": CONTRACT, "design_instance": INSTANCE, "instance_format": None,
        })
        self.assertEqual(analysis, ANALYSIS)
        self.assertEqual(payload(self.initial_model.call_args.args[0])["problem_analysis"], analysis)
        self.assertEqual(selection["selected_ids"], ["CASE-001"])

        quote = "Split converts each permutation into routes; local search improves them"
        full_model = Mock(return_value=json.dumps({
            "findings": [{"claim": quote, "kind": "source",
                          "citations": [{"id": "CASE-001", "field": "description", "quote": quote}]}],
            "supplement_ids": [],
            "gaps": [],
        }))
        budget = Mock(return_value=True)
        result = retrieve_full_materials(
            self.snapshot, selection, analysis, snapshot_events=self.snapshot_events,
            model_call=full_model, model_config=CONFIG, check_budget=budget, check_support=lambda *_: True,
            record=self.records.append,
        )
        full_model.assert_called_once()
        budget.assert_called_once_with(full_model.call_args.args[0])
        self.assertEqual(payload(full_model.call_args.args[0])["problem_analysis"], analysis)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["snapshot_id"], selection["snapshot_id"])

        request_event, response_event, analysis_event = self.records[:3]
        self.assertEqual([row["stage"] for row in self.records[:3]], ["request", "response", "analysis"])
        self.assertTrue(all(row["model_config"] == CONFIG for row in self.records[:3]))
        self.assertEqual(request_event["request"], request)
        self.assertEqual(response_event["response"], raw)
        analysis["hypotheses"].clear()
        self.assertEqual(analysis_event["problem_analysis"], ANALYSIS)

    def test_invalid_responses_stop_before_initial_retrieval(self):
        missing = {key: value for key, value in ANALYSIS.items() if key != "constraints"}
        responses = [
            ("not JSON", "无法解析"),
            ('{"problem":"CVRP","problem":"TSP"}', "重复键"),
            ("[]", "必须是 JSON 对象"),
            (json.dumps(missing), "缺少.*constraints"),
            (json.dumps({**ANALYSIS, "problem_structure": []}), "problem_structure"),
            (json.dumps({**ANALYSIS, "design_needs": []}), "design_needs"),
            (json.dumps({**ANALYSIS, "hypotheses": "assumption"}), "hypotheses"),
            (json.dumps({"problem_gaps": ["容量规则相互冲突"]}), "容量规则相互冲突"),
        ]
        for raw, reason in responses:
            with self.subTest(reason=reason):
                self.records.clear()
                analyst = Mock(return_value=raw)
                with self.assertRaisesRegex(ProblemAnalysisError, reason):
                    self.analyze_and_select(analyst)
                analyst.assert_called_once()
                self.initial_model.assert_not_called()
                self.assertEqual(self.records[-2]["response"], raw)
                self.assertEqual(self.records[-1]["status"], "error")
                self.assertNotIn("problem_analysis", self.records[-1])

    def test_original_contract_changes_stop_before_initial_retrieval(self):
        changes = [
            ("problem", "TSP", "TSP"),
            ("constraints", ["单仓库", *CONTRACT["constraints"][2:]], "同质车辆容量"),
            ("constraints", [*CONTRACT["constraints"][:-1], "固定使用三辆车"], "固定使用三辆车"),
            ("objective", "最小化取整后欧氏距离的总和。", "取整后欧氏距离"),
        ]
        for field, replacement, changed_text in changes:
            with self.subTest(field=field, replacement=replacement):
                raw = json.dumps({**ANALYSIS, field: replacement}, ensure_ascii=False)
                with self.assertRaisesRegex(ProblemAnalysisError, f"{field}.*{changed_text}"):
                    self.analyze_and_select(Mock(return_value=raw))
                self.initial_model.assert_not_called()
                self.assertNotIn("catalog", [event["operation"] for event in self.snapshot_events])

    def test_call_failure_keeps_request_configuration_and_reason(self):
        analyst = Mock(side_effect=TimeoutError("fixture"))
        with self.assertRaisesRegex(ProblemAnalysisError, "TimeoutError"):
            self.analyze_and_select(analyst)
        self.initial_model.assert_not_called()
        self.assertEqual(self.records[0]["request"], analyst.call_args.args[0])
        self.assertEqual(self.records[-1]["model_config"], CONFIG)
        self.assertEqual(self.records[-1]["stage"], "model_call")

    def test_known_instance_format_suffices_and_config_changes_do_not_alter_records(self):
        def respond(_, config):
            config["temperature"] = 1
            return json.dumps({**ANALYSIS, "hypotheses": []})

        instance_format = {"capacity": "positive integer", "customers": "list"}
        analyst = Mock(side_effect=respond)
        result = self.analyze(analyst, design_instance=None, instance_format=instance_format)
        self.assertEqual(result["hypotheses"], [])
        self.assertEqual(payload(analyst.call_args.args[0])["instance_format"], instance_format)
        self.assertEqual(self.records[-1]["model_config"], CONFIG)
        self.assertEqual(CONFIG["temperature"], 0)

    def test_missing_instance_information_stops_before_model_call(self):
        analyst = Mock()
        with self.assertRaisesRegex(ProblemAnalysisError, "design_instance 或 instance_format"):
            self.analyze(analyst, design_instance=None)
        analyst.assert_not_called()
        self.assertEqual(self.records[-1]["stage"], "input")


if __name__ == "__main__":
    unittest.main()
