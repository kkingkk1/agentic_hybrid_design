"""受控验收算法实现者的源码交付、方案缺口与设计版本。"""

import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from scripts.p1_algorithm_implementer import (
    ALGORITHM_IMPLEMENTATION_PROMPT,
    AlgorithmImplementationError,
    implement_algorithm,
)
from scripts.p1_hybrid_designer import design_hybrid
from test_p1_hybrid_designer import ANALYSIS, CASE, CONFIG, DESIGN, FULL, INITIAL, INTERFACE, PROBLEM, sent_request


ACCEPTED = {**DESIGN, "solver_interface": INTERFACE}
SOURCE = """\
def build_routes(instance):
    return [[customer] for customer in instance["customers"]]

def solve(instance, seed, time_limit):
    return build_routes(instance)
"""


def success(version="design-1", code=SOURCE, **extra):
    return json.dumps({"design_version": version, "code": code,
                       "implementation_notes": "先构造完整路线，再使用设计稿定义的入口交付。",
                       **extra}, ensure_ascii=False)


def payload(request):
    return json.loads(request.split("\n\nInput JSON\n", 1)[1])


class AlgorithmImplementerTest(unittest.TestCase):
    def setUp(self):
        self.events = []

    def implement(self, model, **overrides):
        options = {
            "problem_contract": PROBLEM, "design": ACCEPTED, "solver_interface": INTERFACE,
            "design_version": "design-1", "materials": [CASE], "model_config": CONFIG,
            "record": self.events.append, **overrides,
        }
        return implement_algorithm(model_call=model, **options)

    def test_static_acceptance_binds_source_to_accepted_design_and_configuration(self):
        code = 'raise AssertionError("生成源码不能被执行")\n\n' + SOURCE
        raw = success(code=code)
        model = Mock(return_value=raw)
        other_material = {"entry": {"algorithm_id": "ALG-001", "code": "unused"}}
        result = self.implement(model, materials=[other_material, CASE])
        model.assert_called_once()
        request, config = model.call_args.args
        self.assertEqual(config, CONFIG)
        self.assertTrue(request.startswith(ALGORITHM_IMPLEMENTATION_PROMPT))
        self.assertEqual(payload(request), {
            "problem_contract": PROBLEM, "design": ACCEPTED, "solver_interface": INTERFACE,
            "design_version": "design-1", "materials": [CASE], "experience": None,
        })
        self.assertEqual(result, {"status": "pending_evaluation", **json.loads(raw)})
        self.assertEqual([event["stage"] for event in self.events], ["request", "response", "implementation"])
        self.assertEqual(self.events[0]["request"], request)
        self.assertEqual(self.events[1]["response"], raw)
        self.assertTrue(all(event["model_config"] == CONFIG and event["design_version"] == "design-1"
                            for event in self.events))
        result["code"] = ""
        self.assertEqual(self.events[-1]["result"]["code"], code)

    def test_gap_locates_old_design_and_revised_design_gets_its_own_source(self):
        old = deepcopy(ACCEPTED)
        old["components"][0]["outputs"] = "可能包含超容量路线"
        gap = {
            "location": ["components", 0, "outputs"], "design_quote": "可能包含超容量路线",
            "basis": "improve 的输入是容量可行路线", "impact": "局部改进的前置条件无法保证",
            "needed_decision": "明确构造器如何保证输出路线容量可行",
        }
        model = Mock(return_value=json.dumps({"design_version": "design-1", "design_gap": gap}))
        result = self.implement(model, design=old)
        self.assertEqual(result, {"status": "design_gap", "design_version": "design-1", "design_gap": gap})
        self.assertEqual(payload(model.call_args.args[0])["design"], old)
        self.assertNotIn("code", self.events[-1]["result"])
        revised = deepcopy(ACCEPTED)
        revised["components"][0]["outputs"] = "逐条验过容量的完整路线"
        updated = Mock(return_value=success(version="design-2"))
        result = self.implement(updated, design=revised, design_version="design-2")
        self.assertEqual(result["status"], "pending_evaluation")
        self.assertEqual(result["design_version"], "design-2")
        self.assertEqual(payload(updated.call_args.args[0])["design"], revised)
        self.assertEqual(self.events[2]["result"]["design_gap"], gap)
        self.assertEqual(payload(self.events[0]["request"])["design"], old)

    def test_rejects_gap_with_unlocatable_path_or_quote(self):
        gap = {
            "location": ["components", 0, "outputs"], "design_quote": "完整路线",
            "basis": "需说明容量保证", "impact": "不能核对前置条件", "needed_decision": "明确可行化",
        }
        for changes, error in (({"location": ["components", 99, "outputs"]}, "location 无法定位"),
                               ({"design_quote": "并不在设计稿中"}, "design_quote 不在"),
                               ({"basis": ""}, "冲突依据")):
            with self.subTest(changes=changes):
                raw = json.dumps({"design_version": "design-1", "design_gap": {**gap, **changes}})
                with self.assertRaisesRegex(AlgorithmImplementationError, error):
                    self.implement(Mock(return_value=raw))
                self.assertEqual(self.events[-1]["status"], "error")
                self.assertNotIn("result", self.events[-1])

    def test_invalid_source_or_interface_is_not_delivered(self):
        invalid = [
            ("def solve(instance, seed, time_limit)\n    pass", "语法不合格"),
            ("return 1\n" + SOURCE, "语法不合格"),
            ("def build_routes(instance):\n    return []", "顶层普通入口"),
            ("def solve(instance, seed, deadline):\n    return []", "顶层普通入口"),
            ("async def solve(instance, seed, time_limit):\n    return []", "顶层普通入口"),
            (SOURCE + "\ndef solve(instance, seed, time_limit):\n    return []", "顶层普通入口"),
        ]
        for code, error in invalid:
            with self.subTest(code=code):
                raw = success(code=code)
                with self.assertRaisesRegex(AlgorithmImplementationError, error):
                    self.implement(Mock(return_value=raw))
                self.assertEqual(self.events[-2]["response"], raw)
                self.assertNotIn("result", self.events[-1])

    def test_rejects_malformed_response_or_wrong_design_version(self):
        invalid = [
            ("not JSON", "无法解析"),
            (success(version="design-0"), "design_version"),
            (success(code=""), "非空 code"),
            (success(fitness=0), "非空 code"),
        ]
        for raw, error in invalid:
            with self.subTest(error=error), self.assertRaisesRegex(AlgorithmImplementationError, error):
                self.implement(Mock(return_value=raw))

    def test_input_mismatch_and_missing_material_stop_before_model_call(self):
        wrong_contract = deepcopy(PROBLEM)
        wrong_contract["constraints"].pop()
        invalid = [
            ({"problem_contract": wrong_contract}, "目标或硬约束"),
            ({"solver_interface": {**INTERFACE, "time_limit": "秒"}}, "与已接受设计稿不一致"),
            ({"materials": []}, "缺少设计所需材料.*CASE-001"),
        ]
        for overrides, error in invalid:
            with self.subTest(overrides=overrides):
                model = Mock()
                with self.assertRaisesRegex(AlgorithmImplementationError, error):
                    self.implement(model, **overrides)
                model.assert_not_called()
                self.assertEqual(self.events[-1]["stage"], "input")

    def test_call_failure_retains_attempted_request_and_version(self):
        model = Mock(side_effect=TimeoutError("fixture failure"))
        with self.assertRaisesRegex(AlgorithmImplementationError, "TimeoutError"):
            self.implement(model)
        self.assertEqual(self.events[-2]["request"], model.call_args.args[0])
        self.assertEqual(self.events[-1]["stage"], "model_call")
        self.assertEqual(self.events[-1]["status"], "error")
        self.assertEqual(self.events[-1]["design_version"], "design-1")

    def test_accepts_designers_actual_handoff_from_mock_call(self):
        design = design_hybrid(
            PROBLEM, ANALYSIS, INTERFACE, INITIAL, FULL, full_request=sent_request(), model_config=CONFIG,
            model_call=Mock(return_value=json.dumps(DESIGN)), record=lambda _: None,
        )
        model = Mock(return_value=success())
        result = self.implement(model, design=design)
        self.assertEqual(payload(model.call_args.args[0])["design"], design)
        self.assertEqual(result["code"], SOURCE)


if __name__ == "__main__":
    unittest.main()
