"""核验 P0 TSP 实例解析、输入合同与独立评价。"""

import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.p0_tsp_evaluator import (
    DATA_DIR,
    MAX_STDOUT_BYTES,
    EvaluationError,
    evaluate_response,
    load_instance,
    make_solver_input,
)


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "p0_tsp_evaluator.py"
SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1]]


class P0TspEvaluatorTests(unittest.TestCase):
    def evaluate(self, raw, **overrides):
        metadata = {"exit_code": 0, "elapsed_ms": 20, "time_limit_ms": 15000}
        metadata.update(overrides)
        return evaluate_response(SQUARE, raw, **metadata)

    def test_small_paths_match_hand_computed_closed_lengths(self):
        square = self.evaluate(b'{"tour":[0,1,2,3],"objective":-100}')
        self.assertEqual(square, {"valid": True, "objective": 4.0, "declared_objective": -100})
        crossed = self.evaluate(b'{"tour":[0,1,3,2]}')
        self.assertAlmostEqual(crossed["objective"], 2 + 2 * math.sqrt(2))
        triangle = evaluate_response([[0, 0], [3, 0], [0, 4]], b'{"tour":[0,1,2]}',
                                     exit_code=0, elapsed_ms=0, time_limit_ms=15000)
        self.assertEqual(triangle["objective"], 12.0)

    def test_rejects_incomplete_duplicate_and_invalid_tours(self):
        invalid = [
            b'{"tour":[0,1,2]}',
            b'{"tour":[0,1,2,2]}',
            b'{"tour":[0,1,2,3,0]}',
            b'{"tour":[0,1,2,4]}',
            b'{"tour":[0,1,2,-1]}',
            b'{"tour":[0,1,2,true]}',
            b'{"tour":[0,1,2,3.0]}',
            b'{"tour":"0123"}',
        ]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(EvaluationError) as caught:
                self.evaluate(raw)
            self.assertEqual(caught.exception.code, "invalid_tour")

    def test_rejects_invalid_json_schema_and_nonfinite_objectives(self):
        invalid = [
            b'',
            b'\xff',
            b'{"tour":[0,1,2,3]} trailing',
            b'{"tour":[0,1,2,3]} {"tour":[0,1,2,3]}',
            b'{"tour":[0,1,2,3],"tour":[0,1,2,3]}',
            b'{"tour":[0,1,2,3],"extra":1}',
            b'{"objective":4}',
            b'{"tour":[0,1,2,3],"objective":true}',
            b'{"tour":[0,1,2,3],"objective":null}',
            b'{"tour":[0,1,2,3],"objective":NaN}',
            b'{"tour":[0,1,2,3],"objective":Infinity}',
            b'{"tour":[0,1,2,3],"objective":1e999}',
        ]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(EvaluationError):
                self.evaluate(raw)

    def test_rejects_failed_late_or_oversized_outputs(self):
        good = b'{"tour":[0,1,2,3]}'
        checks = [
            ({"exit_code": 7}, good, "execution_failed"),
            ({"elapsed_ms": 15000.001}, good, "timeout"),
            ({}, good + b" " * MAX_STDOUT_BYTES, "stdout_limit"),
            ({"elapsed_ms": float("nan")}, good, "invalid_metadata"),
            ({"elapsed_ms": -1}, good, "invalid_metadata"),
            ({"exit_code": False}, good, "invalid_metadata"),
            ({"time_limit_ms": 0}, good, "invalid_metadata"),
        ]
        for metadata, raw, code in checks:
            with self.subTest(metadata=metadata, code=code), self.assertRaises(EvaluationError) as caught:
                self.evaluate(raw, **metadata)
            self.assertEqual(caught.exception.code, code)
        self.assertTrue(self.evaluate(good, elapsed_ms=15000)["valid"])

    def test_rejects_invalid_coordinate_values(self):
        for coordinates in ([], [[0, True]], [[float("nan"), 0]], [[float("inf"), 0]],
                            [[0, 0, 0]], [[0, "1"]]):
            with self.subTest(coordinates=coordinates), self.assertRaises(EvaluationError) as caught:
                evaluate_response(coordinates, b'{"tour":[0]}', exit_code=0,
                                  elapsed_ms=0, time_limit_ms=15000)
            self.assertEqual(caught.exception.code, "invalid_coordinates")

    def test_loads_all_frozen_instances_and_checks_id(self):
        for size, count in ((50, 5), (200, 10)):
            for index in range(count):
                with self.subTest(size=size, index=index):
                    points = load_instance(f"tsp{size}-{index:03}")
                    self.assertEqual(len(points), size)
                    self.assertTrue(all(len(point) == 2 for point in points))
        for invalid in ("tsp50-005", "tsp200-010", "tsp50-0", "../train50.json", "tsp100-000"):
            with self.subTest(instance=invalid), self.assertRaises(EvaluationError):
                load_instance(invalid)

    def test_rejects_data_whose_checksum_differs_from_manifest(self):
        original = Path.read_bytes

        def altered(path):
            data = original(path)
            return data + b" " if path == DATA_DIR / "train50.json" else data

        with patch.object(Path, "read_bytes", altered), self.assertRaises(EvaluationError) as caught:
            load_instance("tsp50-000")
        self.assertEqual(caught.exception.code, "invalid_instance")

    def test_builds_solver_input_without_accepting_invalid_metadata(self):
        result = make_solver_input(SQUARE, seed=0, time_limit_ms=15000)
        self.assertEqual(result, {"coordinates": SQUARE, "seed": 0, "time_limit_ms": 15000})
        for seed, limit in ((-1, 15000), (True, 15000), (0.5, 15000), (0, 0), (0, True)):
            with self.subTest(seed=seed, limit=limit), self.assertRaises(EvaluationError):
                make_solver_input(SQUARE, seed=seed, time_limit_ms=limit)

    def test_cli_prepares_real_instance_and_evaluates_small_fixture(self):
        prepared = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "input", "--instance", "tsp200-009",
             "--seed", "0", "--time-limit-ms", "15000"], capture_output=True, check=False,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr.decode(errors="replace"))
        payload = json.loads(prepared.stdout)
        self.assertEqual((len(payload["coordinates"]), payload["seed"], payload["time_limit_ms"]),
                         (200, 0, 15000))

        evaluated = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "evaluate", "--coordinates", json.dumps(SQUARE),
             "--exit-code", "0", "--elapsed-ms", "20", "--time-limit-ms", "15000"],
            input=b'{"tour":[0,1,2,3],"objective":99}', capture_output=True, check=False,
        )
        self.assertEqual(evaluated.returncode, 0, evaluated.stderr.decode(errors="replace"))
        self.assertEqual(json.loads(evaluated.stdout),
                         {"valid": True, "objective": 4.0, "declared_objective": 99})

    def test_cli_failure_reports_error_without_score(self):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "evaluate", "--coordinates", json.dumps(SQUARE),
             "--exit-code", "0", "--elapsed-ms", "20", "--time-limit-ms", "15000"],
            input=b'{"tour":[0,1,1,3]}', capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["error"], "invalid_tour")
        self.assertNotIn("objective", payload)


if __name__ == "__main__":
    unittest.main()
