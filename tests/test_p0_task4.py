"""P0任务4的事件、预算和客观评价边界。"""

import base64
import json
import unittest
from unittest.mock import Mock, patch

from scripts import p0_model_runtime as model
from scripts import p0_task4 as task


def event_line(value):
    return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")


class ModelEventTests(unittest.TestCase):
    def make_stream(self, text, usage=None):
        usage = usage if usage is not None else {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20}
        return b"".join(event_line(item) for item in [
            {"type": "thread.started", "thread_id": "test"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
            {"type": "turn.completed", "usage": usage},
        ])

    def test_fragmented_events_preserve_response_and_count_reported_usage_once(self):
        response = {"thought": "simple tour", "code": "print('ok')"}
        raw = self.make_stream(json.dumps(response))
        audit = model.EventAudit()
        for pos in range(0, len(raw), 7):
            audit.feed(raw[pos:pos + 7])
        parsed, usage = audit.finish()
        self.assertEqual(parsed, response)
        self.assertEqual(task._tokens(usage), 120)

    def test_rejects_tool_and_error_events_before_continuing(self):
        for event in ({"type": "item.started", "item": {"type": "command_execution"}},
                      {"type": "error", "message": "retrying"},
                      {"type": "turn.failed"}):
            with self.subTest(event=event), self.assertRaises(model.ModelError):
                model.EventAudit().feed(event_line(event))

    def test_invalid_response_with_known_usage_is_distinct_from_unknown_usage(self):
        audit = model.EventAudit()
        audit.feed(self.make_stream('{"thought":"x","thought":"y","code":"pass"}'))
        with self.assertRaises(model.ResponseFormatError) as caught:
            audit.finish()
        self.assertEqual(task._tokens(caught.exception.usage), 120)
        audit = model.EventAudit()
        audit.feed(self.make_stream(json.dumps({"thought": "x", "code": "pass"}), usage={}))
        with self.assertRaises(model.ModelError) as caught:
            audit.finish()
        self.assertNotIsInstance(caught.exception, model.ResponseFormatError)

    def test_incomplete_events_and_multiple_messages_fail(self):
        audit = model.EventAudit()
        audit.feed(b'{"type":"turn.started"}')
        with self.assertRaises(model.ModelError):
            audit.finish()
        audit = model.EventAudit()
        audit.feed(self.make_stream(json.dumps({"thought": "x", "code": "pass"}))
                   + event_line({"type": "item.completed", "item": {"type": "agent_message", "text": "extra"}}))
        with self.assertRaises(model.ModelError):
            audit.finish()

    def test_command_disables_tools_and_uses_existing_subscription_provider(self):
        command = model.command(model.Path("codex.exe"), model.Path("work"), model.Path("schema.json"))
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--output-schema", command)
        self.assertIn("model_providers.p0_chatgpt_https.request_max_retries=0", command)
        self.assertIn("model_providers.p0_chatgpt_https.stream_max_retries=0", command)
        self.assertNotIn("OPENAI_API_KEY", model.child_environment())


class EvaluationTests(unittest.TestCase):
    def test_independent_objective_ignores_solver_claim(self):
        response = json.dumps({"tour": [0, 1, 2, 3], "objective": 999}).encode("utf-8")
        result = {"reason": "exited", "exit_code": 0, "elapsed_seconds": 1,
                  "stdout_b64": base64.b64encode(response).decode("ascii")}
        checked = task._evaluate([[0, 0], [1, 0], [1, 1], [0, 1]], result)
        self.assertTrue(checked["valid"])
        self.assertEqual(checked["objective"], 4.0)
        self.assertEqual(checked["declared_objective"], 999)

    def test_nonzero_exit_and_invalid_tour_are_failures(self):
        response = json.dumps({"tour": [0, 0, 1, 2]}).encode("utf-8")
        result = {"reason": "exited", "exit_code": 0, "elapsed_seconds": 1,
                  "stdout_b64": base64.b64encode(response).decode("ascii")}
        self.assertFalse(task._evaluate([[0, 0], [1, 0], [1, 1], [0, 1]], result)["valid"])
        result["reason"] = "timeout"
        self.assertEqual(task._evaluate([[0, 0]], result), {"valid": False, "code": "timeout"})

    def test_resource_wait_retries_without_turning_other_errors_into_retries(self):
        ledger = Mock()
        with patch.object(task.sandbox, "run_candidate", side_effect=[OSError("资源检查不满足 P0 条件"), {"ok": True}]) as run, \
                patch.object(task.time, "sleep"):
            self.assertEqual(task._candidate("test", 0, b"pass", b"", build=True,
                                             deadline=float("inf"), ledger=ledger), {"ok": True})
            self.assertEqual(run.call_count, 2)
            ledger.add.assert_called_once()
        with patch.object(task.sandbox, "run_candidate", side_effect=OSError("other")) as run:
            with self.assertRaises(OSError):
                task._candidate("test", 0, b"pass", b"", build=True, deadline=float("inf"), ledger=ledger)
            run.assert_called_once()

    def test_deadline_stops_new_work(self):
        with patch.object(task.time, "monotonic", return_value=100), self.assertRaises(task.StopRun):
            task._remaining(120, 20)

    def test_existing_attempt_cannot_reset_budget(self):
        existing = Mock()
        existing.read_bytes.return_value = b'{"event":"model_attempt_started","attempt":1}\n'
        root = Mock()
        root.glob.return_value = [existing]
        with patch.object(task, "RUNS", root), self.assertRaises(task.StopRun):
            task._new_batch()

    def test_dynamic_cpu_parking_does_not_change_stable_mapping(self):
        first = {"workers": [{"slot": 0, "logical_processor": 16, "parked": False}], "instances": []}
        second = {"workers": [{"slot": 0, "logical_processor": 16, "parked": True}], "instances": []}
        self.assertEqual(task._stable_mapping(first), task._stable_mapping(second))


if __name__ == "__main__":
    unittest.main()
