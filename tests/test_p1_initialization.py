"""用正式快照和假模型验收 P1 初始化及方案修订。"""

import json
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from scripts import p1_library_reader as library
from scripts.p1_initialization import run_initialization
from test_p1_algorithm_implementer import SOURCE, success
from test_p1_hybrid_designer import ANALYSIS, CASE_QUOTE, CONFIG, DESIGN, INTERFACE, PROBLEM, SELECTION


ANALYST = "problem_analysis"
INITIAL = "retriever_initial_selection"
FULL = "retriever_full_materials"
DESIGNER = "hybrid_design"
IMPLEMENTER = "algorithm_implementation"
CONFIGS = {role: {**CONFIG, "temperature": temperature}
           for role, temperature in ((ANALYST, 0), ("retriever", 0.1), (DESIGNER, 0.2), (IMPLEMENTER, 0.3))}
FINDINGS = [
    {"claim": CASE_QUOTE, "kind": "source",
     "citations": [{"id": "CASE-001", "field": "description", "quote": CASE_QUOTE}]},
    {"claim": "参考解码器可无条件处理可变车数", "kind": "unverified", "citations": []},
]
GAPS = ["参考解码器是否支持可变车数仍待核实"]
FIXTURE = {**DESIGN, "evidence_use": [
    {"finding_index": 0, "use": "supporting", "conditions": "参考组件衔接"},
    {"finding_index": 1, "use": "hypothesis", "conditions": "使用新构造器，暂不依赖该判断"},
]}


def receipt(supplement_ids=(), findings=FINDINGS):
    return {"findings": findings, "gaps": GAPS, "supplement_ids": list(supplement_ids)}


def json_text(value):
    return json.dumps(value, ensure_ascii=False)


def payload(request):
    return json.loads(request.split("\n\nInput JSON\n", 1)[1])


def reported_gap(version, draft):
    return json_text({"design_version": version, "design_gap": {
        "location": ["components", 0, "outputs"],
        "design_quote": draft["components"][0]["outputs"],
        "basis": "局部搜索的输入必须是容量可行路线", "impact": "局部搜索前置条件未被满足",
        "needed_decision": "明确解码器如何保证完整路线容量可行",
    }})


class InitializationTest(unittest.TestCase):
    def run_chain(self, model, **overrides):
        options = {
            "initialization_id": "fixture-cvrp", "model_configs": CONFIGS,
            "model_call": model, "check_budget": Mock(return_value=True), "check_support": lambda *_: True,
            "max_revisions": 1, "instance_format": "CVRP 坐标、需求和容量",
            **overrides,
        }
        return run_initialization(PROBLEM, INTERFACE, **options)

    def test_success_uses_final_supplement_request_and_retains_uncertainty(self):
        model = Mock(side_effect=[
            json_text(ANALYSIS), json_text(SELECTION),
            json_text(receipt(["ALG-006"])), json_text(receipt()),
            json_text(FIXTURE), success(),
        ])
        budget, forwarded = Mock(return_value=True), []
        result = self.run_chain(model, check_budget=budget, record=forwarded.append)
        stages, requests, configs = zip(*(call.args for call in model.call_args_list), strict=True)
        self.assertEqual(stages, (ANALYST, INITIAL, FULL, FULL, DESIGNER, IMPLEMENTER))
        self.assertEqual(configs, (CONFIGS[ANALYST], CONFIGS["retriever"], CONFIGS["retriever"],
                                   CONFIGS["retriever"], CONFIGS[DESIGNER], CONFIGS[IMPLEMENTER]))
        self.assertEqual([call.args[0] for call in budget.call_args_list], list(requests))
        initial, first, final, design, impl = [payload(request) for request in requests[1:]]
        for data in (initial, first, final, design):
            self.assertEqual(data["problem_analysis"], ANALYSIS)
        self.assertEqual(len(first["materials"]), 1)
        self.assertEqual(len(final["materials"]), 2)
        self.assertEqual(design["materials"], final["materials"])
        self.assertEqual(design["initial_selection"]["snapshot_id"], library.FORMAL_SNAPSHOT_ID)
        self.assertEqual(design["initial_selection"]["snapshot_id"], design["full_retrieval"]["snapshot_id"])
        self.assertEqual(design["full_retrieval"]["file_versions"], final["file_versions"])
        self.assertEqual(design["full_retrieval"]["gaps"], GAPS)
        self.assertEqual(design["full_retrieval"]["findings"][1]["kind"], "unverified")
        self.assertEqual(impl["design_version"], result["design_version"])
        self.assertEqual(impl["design"], result["design"])
        self.assertEqual(impl["materials"], first["materials"])
        self.assertEqual(result["status"], "pending_evaluation")
        self.assertEqual(result["code"], SOURCE)
        self.assertEqual(result["records"], forwarded)
        self.assertEqual([row["event_index"] for row in forwarded], list(range(1, len(forwarded) + 1)))
        self.assertTrue(all(row["initialization_id"] == "fixture-cvrp" for row in forwarded))
        sent = [row for row in forwarded if row.get("stage") == "send"]
        self.assertEqual([forwarded[row["request_event"] - 1]["request"] for row in sent], list(requests))

    def test_denied_supplement_keeps_only_sent_materials_and_checks_downstream_budget(self):
        for allow_design in (True, False):
            with self.subTest(allow_design=allow_design):
                def preflight(request):
                    data = payload(request)
                    if "problem_contract" not in data and len(data.get("materials", [])) > 1:
                        return False
                    if "full_retrieval" in data:
                        return allow_design
                    return True

                model = Mock(side_effect=[
                    json_text(ANALYSIS), json_text(SELECTION), json_text(receipt(["ALG-006"])),
                    json_text(FIXTURE), success(),
                ])
                budget = Mock(side_effect=preflight)
                result = self.run_chain(model, check_budget=budget)
                called = [call.args[0] for call in model.call_args_list]
                if allow_design:
                    self.assertEqual(called, [ANALYST, INITIAL, FULL, DESIGNER, IMPLEMENTER])
                    self.assertEqual(result["status"], "pending_evaluation")
                    self.assertEqual(result["full_retrieval"]["loaded_ids"], ["CASE-001"])
                    self.assertEqual(result["full_retrieval"]["findings"][0]["kind"], "source")
                    self.assertTrue(any("预算不足" in gap for gap in result["full_retrieval"]["gaps"]))
                    self.assertEqual(result["materials"], payload(model.call_args_list[2].args[1])["materials"])
                else:
                    self.assertEqual(called, [ANALYST, INITIAL, FULL])
                    self.assertEqual(result["stage"], DESIGNER)
                    self.assertEqual(result["status"], "stopped")
                    self.assertIn("请求预算不足", result["reason"])
                    self.assertNotIn("code", result)
                self.assertEqual(budget.call_count, model.call_count + (1 if allow_design else 2))

    def test_no_retrieval_evidence_or_budget_stops_before_design(self):
        cases = [
            ({"algorithms": [], "cases": []}, True, receipt(), [ANALYST, INITIAL], "未选中材料"),
            (SELECTION, True, receipt(findings=FINDINGS[1:]), [ANALYST, INITIAL, FULL], "没有可交接"),
            (SELECTION, False, receipt(), [ANALYST, INITIAL], "预算不足"),
            (SELECTION, None, receipt(), [ANALYST, INITIAL], "预算无法核验"),
        ]
        for selection, allowed, full_response, stages, reason in cases:
            with self.subTest(reason=reason):
                model = Mock(side_effect=[json_text(ANALYSIS), json_text(selection), json_text(full_response)])
                result = self.run_chain(model, check_budget=lambda request: (
                    allowed if "file_versions" in payload(request) else True
                ))
                self.assertEqual([call.args[0] for call in model.call_args_list], stages)
                self.assertEqual(result["stage"], FULL)
                self.assertEqual(result["status"], "stopped")
                self.assertIn(reason, result["reason"])
                self.assertNotIn("code", result)

    def test_changed_snapshot_and_inconsistent_model_stop_without_downstream_calls(self):
        read_bytes = library._read_bytes
        changed = False
        target = library.FORMAL_ROOT / "cases/CASE-001/CASE-001.json"

        def model_reply(stage, request, config):
            nonlocal changed
            if stage == ANALYST:
                return json_text(ANALYSIS)
            changed = True
            return json_text(SELECTION)

        def changed_file(path):
            value = read_bytes(path)
            return value + b"\n" if changed and path == target else value

        model = Mock(side_effect=model_reply)
        with patch.object(library, "_read_bytes", side_effect=changed_file):
            stopped = self.run_chain(model)
        self.assertEqual([call.args[0] for call in model.call_args_list], [ANALYST, INITIAL])
        self.assertEqual(stopped["stage"], FULL)
        self.assertIn("CASE-001.json", stopped["reason"])
        different_model = {**CONFIGS, DESIGNER: {**CONFIGS[DESIGNER], "version": "different"}}
        model = Mock()
        stopped = self.run_chain(model, model_configs=different_model)
        model.assert_not_called()
        self.assertEqual(stopped["stage"], "input")
        self.assertIn("同一模型底座和版本", stopped["reason"])

    def test_gap_reaches_designer_and_revised_design_reaches_implementer(self):
        old, new = deepcopy(FIXTURE), deepcopy(FIXTURE)
        old["components"][0]["outputs"] = "可能包含超容量路线"
        new["components"][0]["outputs"] = "经容量验证的完整路线"
        new["change_summary"] = "构造器在交接前按容量拆分超载路线"
        model = Mock(side_effect=[
            json_text(ANALYSIS), json_text(SELECTION), json_text(receipt()), json_text(old),
            reported_gap("design-1", old), json_text(new), success(version="design-2"),
        ])
        result = self.run_chain(model)
        self.assertEqual([call.args[0] for call in model.call_args_list],
                         [ANALYST, INITIAL, FULL, DESIGNER, IMPLEMENTER, DESIGNER, IMPLEMENTER])
        old_request = payload(model.call_args_list[4].args[1])
        revision = payload(model.call_args_list[5].args[1])
        self.assertEqual(revision["revision"]["previous_design"], old_request["design"])
        self.assertEqual(revision["revision"]["previous_version"], "design-1")
        self.assertEqual(revision["revision"]["design_gap"]["design_quote"], old["components"][0]["outputs"])
        self.assertEqual(revision["materials"], payload(model.call_args_list[3].args[1])["materials"])
        new_request = payload(model.call_args_list[6].args[1])
        self.assertEqual(new_request["design"]["components"], new["components"])
        self.assertEqual(new_request["design_version"], "design-2")
        self.assertEqual(result["status"], "pending_evaluation")
        self.assertEqual(result["design_version"], "design-2")
        self.assertEqual(result["code"], SOURCE)
        event = next(row for row in result["records"] if row.get("stage") == "revision")
        self.assertEqual((event["previous_version"], event["design_version"]), ("design-1", "design-2"))
        self.assertEqual(event["change_summary"], new["change_summary"])

    def test_revision_limit_or_ineffective_revision_returns_no_source(self):
        old = deepcopy(FIXTURE)
        old["components"][0]["outputs"] = "可能包含超容量路线"
        revised = deepcopy(old)
        revised["components"][0]["outputs"] = "仍可能生成超容量路线"
        revised["change_summary"] = "记录剩余风险"
        unchanged = {**old, "change_summary": "声称已处理容量"}
        for next_design, next_gap, stages, reason in (
            (revised, reported_gap("design-2", revised), [DESIGNER, IMPLEMENTER], "方案修订上限"),
            (unchanged, None, [DESIGNER], "修订稿未改变"),
        ):
            with self.subTest(reason=reason):
                model = Mock(side_effect=[
                    json_text(ANALYSIS), json_text(SELECTION), json_text(receipt()), json_text(old),
                    reported_gap("design-1", old), json_text(next_design), next_gap,
                ])
                stopped = self.run_chain(model)
                self.assertEqual([call.args[0] for call in model.call_args_list][5:], stages)
                self.assertEqual(stopped["status"], "stopped")
                self.assertIn(reason, stopped["reason"])
                self.assertNotIn("code", stopped)
                self.assertTrue(any(row["status"] == "design_gap" for row in stopped["records"]))


if __name__ == "__main__":
    unittest.main()
