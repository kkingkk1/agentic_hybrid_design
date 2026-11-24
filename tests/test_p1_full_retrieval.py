"""任务 2.3 使用正式快照和受控回调的验收。"""

import json
import unittest
from unittest.mock import Mock, patch

from scripts import p1_library_reader as library
from scripts.p1_full_retrieval import FULL_RETRIEVAL_PROMPT, retrieve_full_materials
from scripts.p1_retriever import RetrieverError, select_initial_candidates


CONFIG = {"model": "fixture-retriever", "version": "1", "temperature": 0}
PROBLEM = {"problem": "CVRP", "design_needs": ["排列解码", "局部改进"]}
CASE_QUOTE = "Split converts each permutation into routes; local search improves them"


def finding(claim, entry_id="CASE-001", quote=CASE_QUOTE, field="description", kind="paraphrase"):
    return {"claim": claim, "kind": kind, "citations": [{"id": entry_id, "field": field, "quote": quote}]}


def response(*findings, supplement_ids=(), gaps=()):
    return json.dumps({"findings": list(findings), "supplement_ids": list(supplement_ids), "gaps": list(gaps)})


def payload(request):
    return json.loads(request.split("\n\nInput JSON\n", 1)[1])


class FullRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.records = []
        self.snapshot = library.RetrievalSnapshot(record=self.events.append)
        self.support = Mock(return_value=True)

    def initial(self, ids=("ALG-001", "ALG-002", "CASE-001")):
        selected = {
            group: [{"id": entry_id, "reason": "Review the design mechanism."}
                    for entry_id in ids if entry_id.startswith(prefix)]
            for group, prefix in (("algorithms", "ALG"), ("cases", "CASE"))
        }
        return select_initial_candidates(
            self.snapshot, PROBLEM, snapshot_events=self.events,
            model_call=lambda _: json.dumps(selected), record=self.records.append, model_config=CONFIG,
        )

    def retrieve(self, initial, model, budget, **options):
        return retrieve_full_materials(
            self.snapshot, initial, PROBLEM, snapshot_events=self.events, model_call=model, check_budget=budget,
            check_support=self.support, record=self.records.append, **{"model_config": CONFIG, **options},
        )

    def test_full_request_version_and_actual_evidence(self):
        initial = self.initial()
        grounded = finding(
            "CASE-001 passes the crossover permutation to Split before local search.",
            quote="Order crossover copies a segment from the first parent and fills the remaining "
                  "positions in the second parent's order, producing a new permutation.",
        )
        grounded["citations"].extend([
            {"id": "CASE-001", "field": "description",
             "quote": "Pass the permutation to Split with the first parent's route count."},
            {"id": "CASE-001", "field": "description",
             "quote": "Improve the decoded routes using route moves, including SWAP*."},
        ])
        unsupported = finding("ALG-006的实现与CASE-001中的交叉相同。")
        fake_quote = finding("CASE-001 guarantees the capacity bound.", quote="absent evidence")
        raw = response(grounded, unsupported, fake_quote)
        model, budget = Mock(return_value=raw), Mock(return_value=True)

        result = self.retrieve(initial, model, budget)

        request = model.call_args.args[0]
        budget.assert_called_once_with(request)
        self.assertTrue(request.startswith(FULL_RETRIEVAL_PROMPT))
        actual = payload(request)
        self.assertEqual(actual["problem_analysis"], PROBLEM)
        expected = library.LibraryReader(library.FORMAL_ROOT, manifest=library.FORMAL_MANIFEST).load(
            ["ALG-001", "ALG-002", "CASE-001"],
        )
        self.assertEqual(actual["materials"], expected)
        self.assertIn("FILE:", actual["materials"][-1]["entry"]["code"])
        self.assertTrue(any("ALG-001" in path and "Split.cpp" in path for path in actual["file_versions"]))
        self.assertEqual(actual["file_versions"], self.events[-1]["files"])
        self.assertEqual(result["loaded_ids"], ["ALG-001", "ALG-002", "CASE-001"])
        self.assertEqual(result["manifest_sha256"], initial["manifest_sha256"])
        self.assertEqual(result["model_config"], CONFIG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([item["kind"] for item in result["findings"]], ["paraphrase", "unverified", "unverified"])
        self.assertEqual(self.support.call_count, 1)
        self.assertGreater(result["findings"][0]["citations"][0]["line"], 0)
        self.assertTrue(any("ALG-006" in gap for gap in result["gaps"]))
        self.assertIn(raw, [row.get("response") for row in self.records])

    def test_supplement_resends_only_actual_materials_with_new_versions(self):
        item = finding("CASE-001 decodes a permutation into routes.")
        model = Mock(side_effect=[response(item, supplement_ids=["ALG-006", "CASE-999"]), response(item)])
        budget = Mock(return_value=True)
        result = self.retrieve(self.initial(("CASE-001",)), model, budget)
        self.assertEqual(result["loaded_ids"], ["CASE-001", "ALG-006"])
        self.assertEqual([event["ids"] for event in self.events if event["operation"] == "load"],
                         [["CASE-001"], ["ALG-006"]])
        self.assertEqual(model.call_args_list, budget.call_args_list)
        self.assertEqual(len(payload(model.call_args_list[0].args[0])["materials"]), 1)
        self.assertEqual(len(payload(model.call_args_list[1].args[0])["materials"]), 2)
        self.assertTrue(any("CASE-999" in gap for gap in result["gaps"]))

    def test_denied_supplement_keeps_only_previously_supported_evidence(self):
        initial = self.initial(("CASE-001",))
        for findings, decision, status in (
            ([finding("CASE-001 uses Split.")], False, "ok"),
            ([], None, "stopped"),
        ):
            with self.subTest(status=status):
                model = Mock(return_value=response(*findings, supplement_ids=["ALG-006"]))
                budget = Mock(side_effect=[True, decision])
                result = self.retrieve(initial, model, budget)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["loaded_ids"], ["CASE-001"])
                self.assertEqual(model.call_count, 1)
                self.assertEqual(budget.call_count, 2)
                self.assertTrue(any("预算" in gap for gap in result["gaps"]))
                self.assertFalse(any("ALG-006/ALG-006.md" in path for path in result["file_versions"]))

    def test_budget_must_affirm_initial_call(self):
        initial = self.initial(("CASE-001",))
        for budget in (Mock(return_value=False), Mock(return_value=None), Mock(side_effect=TimeoutError)):
            with self.subTest(budget=budget):
                model = Mock()
                result = self.retrieve(initial, model, budget)
                model.assert_not_called()
                self.assertEqual(result["status"], "stopped")
                self.assertEqual(result["loaded_ids"], [])
                self.assertTrue(any("预算" in gap for gap in result["gaps"]))

    def test_empty_initial_selection_and_known_supplement(self):
        initial = self.initial(())
        model, budget = Mock(return_value=response(finding("CASE-001 uses Split."))), Mock(return_value=True)
        result = self.retrieve(initial, model, budget)
        self.assertEqual(result["status"], "stopped")
        budget.assert_not_called()
        model.assert_not_called()
        self.assertNotIn("load", [event["operation"] for event in self.events])
        result = self.retrieve(initial, model, budget, empty_selection_supplement=["CASE-001"])
        self.assertEqual(result["loaded_ids"], ["CASE-001"])
        self.assertTrue(any("未选中材料" in gap for gap in result["gaps"]))

    def test_snapshot_changes_or_model_mismatch_stop_before_budget(self):
        initial = self.initial(("CASE-001",))
        model, budget = Mock(), Mock()
        with self.assertRaisesRegex(RetrieverError, "模型底座和版本"):
            self.retrieve(initial, model, budget, model_config={**CONFIG, "version": "2"})
        with self.assertRaisesRegex(RetrieverError, "目录.*快照版本"):
            self.retrieve({**initial, "snapshot_id": "other"}, model, budget)
        read = library._read_bytes

        def changed(path):
            value = read(path)
            return value + b"\n" if path.name == "CASE-001.json" else value

        with patch.object(library, "_read_bytes", side_effect=changed):
            with self.assertRaisesRegex(RetrieverError, "CASE-001.json"):
                self.retrieve(initial, model, budget)
        budget.assert_not_called()
        model.assert_not_called()

    def test_exact_quote_still_requires_support_for_claim(self):
        initial = self.initial(("CASE-001",))
        self.support.return_value = None
        model = Mock(return_value=response(finding("CASE-001 guarantees optimality.")))
        result = self.retrieve(initial, model, Mock(return_value=True))
        self.support.assert_called_once()
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["findings"][0]["kind"], "unverified")
        self.assertTrue(any("尚未确认支撑" in gap for gap in result["gaps"]))

    def test_algorithm_file_and_source_citations_are_located(self):
        initial = self.initial(("ALG-001",))

        def model(request):
            material = payload(request)["materials"][0]
            file = material["entry"]["code"]["files"][0]
            line = next(line for line in file["content"].splitlines() if line.strip())
            source = next(line for line in material["source"]["content"].splitlines() if line.strip())
            return response(
                finding(line, "ALG-001", line, "code:" + file["path"], "source"),
                finding(source, "ALG-001", source, "source", "source"),
            )

        result = self.retrieve(initial, model, Mock(return_value=True))
        self.assertEqual([item["kind"] for item in result["findings"]], ["source", "source"])
        self.assertEqual(self.support.call_count, 2)

    def test_malformed_response_records_raw_text_and_stops(self):
        initial = self.initial(("CASE-001",))
        raw = '{"findings":[],"findings":[],"supplement_ids":[],"gaps":[]}'
        with self.assertRaisesRegex(RetrieverError, "重复键"):
            self.retrieve(initial, Mock(return_value=raw), Mock(return_value=True))
        self.assertEqual(self.records[-2]["response"], raw)
        self.assertEqual(self.records[-1]["status"], "error")


if __name__ == "__main__":
    unittest.main()
