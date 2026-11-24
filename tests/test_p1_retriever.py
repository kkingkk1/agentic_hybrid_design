"""用正式快照和可控模型验收 Retriever 初选。"""

import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from scripts import p1_library_reader as library
from scripts import p1_retriever as retriever


PROBLEM_ANALYSIS = {
    "problem": "CVRP",
    "problem_structure": "将客户分配到多条车辆路线，并确定各路线的访问顺序。",
    "objective": "最小化按未取整欧氏距离计算的总路线距离。",
    "constraints": ["单仓库", "同质车辆容量", "每位客户服务一次，需求不拆分", "使用车辆数可变"],
    "design_needs": ["考察将客户排列解码为容量可行路线的方法", "查找解码与局部改进相衔接的案例"],
}


class RetrieverTest(unittest.TestCase):
    def setUp(self):
        self.snapshot_events = []
        self.records = []
        self.snapshot = library.RetrievalSnapshot(record=self.snapshot_events.append)

    def select(self, model_call):
        return retriever.select_initial_candidates(
            self.snapshot,
            PROBLEM_ANALYSIS,
            snapshot_events=self.snapshot_events,
            model_call=model_call,
            record=self.records.append,
        )

    def test_full_catalog_request_and_successful_handoff(self):
        selection = {
            "cases": [
                {"id": "CASE-037", "reason": "A second case."},
                {"id": "CASE-001", "reason": "Combines Split decoding and route local search."},
            ],
            "algorithms": [
                {"id": "ALG-006", "reason": "Supplies an order crossover component."},
                {"id": "ALG-001", "reason": "将客户排列解码为路线，硬容量条件待核实。"},
            ],
        }
        response = "\n" + json.dumps(selection, ensure_ascii=False) + "\n"
        model = Mock(return_value=response)
        with patch.object(self.snapshot, "load") as load:
            result = self.select(model)
        load.assert_not_called()
        model.assert_called_once()

        request = model.call_args.args[0]
        instructions, payload = request.split("\n\nInput JSON\n", 1)
        self.assertEqual(instructions, retriever.INITIAL_SELECTION_PROMPT)
        for fixture_value in ("CVRP", "ALG-001", "CASE-001"):
            self.assertNotIn(fixture_value, instructions)
        catalog = library.LibraryReader(library.FORMAL_ROOT, manifest=library.FORMAL_MANIFEST).catalog()
        self.assertEqual((len(catalog["algorithms"]), len(catalog["cases"])), (65, 35))
        self.assertEqual(json.loads(payload), {"problem_analysis": PROBLEM_ANALYSIS, **catalog})
        self.assertEqual([event["operation"] for event in self.snapshot_events], ["pin", "catalog"])

        version = {
            "snapshot_id": library.FORMAL_SNAPSHOT_ID,
            "manifest_sha256": hashlib.sha256(library.FORMAL_MANIFEST.read_bytes()).hexdigest(),
        }
        expected = {
            "selection": selection,
            "selected_ids": ["ALG-006", "ALG-001", "CASE-037", "CASE-001"],
            **version,
        }
        self.assertEqual(result, expected)
        self.assertEqual([event["stage"] for event in self.records], ["request", "response", "selection"])
        self.assertEqual(self.records[0]["request"], request)
        self.assertEqual(self.records[1]["response"], response)
        for event in self.records:
            self.assertEqual(event["status"], "ok")
            self.assertEqual({key: event[key] for key in version}, version)
        self.assertEqual({key: self.records[-1][key] for key in expected}, expected)
        result["selection"]["algorithms"].clear()
        self.assertEqual(self.records[-1]["selection"], selection)

    def test_empty_groups_advance_without_inventing_ids(self):
        algorithm = {"id": "ALG-001", "reason": "Permutation decoding."}
        case = {"id": "CASE-001", "reason": "Decoding followed by local search."}
        for algorithms, cases in (([], [case]), ([algorithm], []), ([], [])):
            with self.subTest(algorithms=algorithms, cases=cases):
                selection = {"algorithms": algorithms, "cases": cases}
                result = self.select(Mock(return_value=json.dumps(selection)))
                self.assertEqual(result["selection"], selection)
                self.assertEqual(result["selected_ids"], [item["id"] for item in algorithms + cases])
                self.assertEqual(result["snapshot_id"], library.FORMAL_SNAPSHOT_ID)
                if not algorithms and not cases:
                    self.assertEqual(self.records[-1]["message"], "本轮未选中材料")

    def test_invalid_responses_are_recorded_and_never_handed_off(self):
        valid = {"id": "ALG-001", "reason": "Permutation decoding."}
        invalid = [
            ("not JSON", "无法解析"),
            ("[]", "仅含 algorithms 和 cases"),
            ('{"algorithms":[]}', "仅含 algorithms 和 cases"),
            ('{"algorithms":[],"cases":[],"notes":[]}', "仅含 algorithms 和 cases"),
            ('{"algorithms":[],"algorithms":[],"cases":[]}', "重复键"),
            ('{"algorithms":[{"id":"ALG-001","id":"ALG-006","reason":"r"}],"cases":[]}', "重复键"),
            ('{"algorithms":{},"cases":[]}', "必须是数组"),
            ('{"algorithms":[{"id":"ALG-001","reason":NaN}],"cases":[]}', "非有限数值"),
            (json.dumps({"algorithms": [valid], "cases": [valid]}), "不属于该组目录"),
        ]
        for items, error in (
            (["ALG-001"], "每项必须仅含"),
            ([{"id": "ALG-001"}], "每项必须仅含"),
            ([{**valid, "score": 1}], "每项必须仅含"),
            ([{**valid, "id": 1}], "不属于该组目录"),
            ([{**valid, "id": "ALG-001 "}], "不属于该组目录"),
            ([{**valid, "id": "ALG-999"}], "不属于该组目录"),
            ([{**valid, "reason": "\t\n "}], "非空字符串"),
            ([{**valid, "reason": None}], "非空字符串"),
            ([valid, valid], "重复选择"),
        ):
            invalid.append((json.dumps({"algorithms": items, "cases": []}), error))
        for response, error in invalid:
            with self.subTest(response=response):
                self.records.clear()
                model = Mock(return_value=response)
                with self.assertRaisesRegex(retriever.RetrieverError, error):
                    self.select(model)
                model.assert_called_once()
                self.assertEqual([event["status"] for event in self.records], ["ok", "ok", "error"])
                self.assertEqual(self.records[1]["response"], response)
                self.assertEqual(self.records[-1]["stage"], "selection")
                self.assertIn(error, self.records[-1]["reason"])
                self.assertNotIn("selection", self.records[-1])

    def test_truncated_request_is_rejected_before_model_call(self):
        model = Mock()
        encode = json.dumps

        def truncate(payload, **options):
            return encode({**payload, "cases": payload["cases"][:-1]}, **options)

        with patch.object(retriever.json, "dumps", side_effect=truncate):
            with self.assertRaisesRegex(retriever.RetrieverError, "候选目录不一致"):
                self.select(model)
        model.assert_not_called()
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["stage"], "request")
        self.assertEqual(self.records[0]["status"], "error")

    def test_changed_snapshot_is_rejected_before_model_call(self):
        model = Mock()
        read_bytes = library._read_bytes
        target = library.FORMAL_ROOT / "cases/CASE-001/CASE-001.json"

        def read_changed_file(path):
            value = read_bytes(path)
            return value + b"\n" if path == target else value

        with patch.object(library, "_read_bytes", side_effect=read_changed_file):
            with self.assertRaisesRegex(retriever.RetrieverError, "CASE-001.json"):
                self.select(model)
        model.assert_not_called()
        self.assertEqual(self.snapshot_events[-1]["status"], "error")
        self.assertEqual(self.records[0]["stage"], "catalog")
        self.assertEqual(self.records[0]["status"], "error")

    def test_missing_catalog_event_does_not_reuse_an_earlier_success(self):
        model = Mock()
        self.snapshot.catalog()
        with patch.object(self.snapshot, "_record_event"):
            with self.assertRaisesRegex(retriever.RetrieverError, "本次目录读取"):
                self.select(model)
        model.assert_not_called()
        self.assertEqual(self.records[0]["stage"], "catalog")
        self.assertEqual(self.records[0]["status"], "error")

    def test_model_error_retains_the_attempted_request(self):
        model = Mock(side_effect=TimeoutError("fixture timeout"))
        with self.assertRaisesRegex(retriever.RetrieverError, "TimeoutError"):
            self.select(model)
        model.assert_called_once()
        self.assertEqual(self.records[0]["request"], model.call_args.args[0])
        self.assertEqual(self.records[-1]["stage"], "model_call")
        self.assertEqual(self.records[-1]["status"], "error")
        self.assertNotIn("selection", self.records[-1])


if __name__ == "__main__":
    unittest.main()
