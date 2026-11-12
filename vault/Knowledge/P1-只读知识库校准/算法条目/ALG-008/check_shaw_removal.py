"""检查 Shaw 请求选择及同请求节点的移除。"""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("alg_008_shaw", Path(__file__).with_name("shaw_removal.py"))
SHAW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHAW)


class Draws:
    def __init__(self, *values):
        self.values = iter(values)

    def random(self):
        return next(self.values)


class ShawTests(unittest.TestCase):
    def test_related_pairs_removed_and_inputs_preserved(self):
        routes = [["ap", "ad", "bp", "bd"], ["cp", "cd"]]
        mapping = {"ap": "a", "ad": "a", "bp": "b", "bd": "b", "cp": "c", "cd": "c"}
        distances = {("a", "b"): 1, ("a", "c"): 3}
        result, removed = SHAW.shaw_removal(routes, mapping, 2, 2, lambda a, b: distances[a, b], Draws(0, 0, 0))
        self.assertEqual(removed, ["a", "b"])
        self.assertEqual(result, [[], ["cp", "cd"]])
        self.assertEqual(routes, [["ap", "ad", "bp", "bd"], ["cp", "cd"]])

    def test_rank_bias_and_empty_removal(self):
        routes, mapping = [["a", "b", "c"]], {"a": "a", "b": "b", "c": "c"}
        _, removed = SHAW.shaw_removal(routes, mapping, 2, 2, lambda a, b: {"b": 1, "c": 2}[b], Draws(0, 0, 0.8))
        self.assertEqual(removed, ["a", "c"])
        _, selected = SHAW.shaw_removal(routes, mapping, 2, 10**400, lambda a, b: {"b": 1, "c": 2}[b], Draws(0, 0, 0.8))
        self.assertEqual(selected, ["a", "b"])
        self.assertEqual(SHAW.shaw_removal(routes, mapping, 0, 1, lambda a, b: 0, Draws()), (routes, []))

    def test_invalid_input_and_relation(self):
        with self.assertRaises(ValueError):
            SHAW.shaw_removal([[1], [2]], {1: "a", 2: "a"}, 1, 1, lambda a, b: 0, Draws(0))
        with self.assertRaises(ValueError):
            SHAW.shaw_removal([[1]], {1: "a"}, 2, 1, lambda a, b: 0, Draws(0))
        with self.assertRaises(ValueError):
            SHAW.shaw_removal([[1, 2]], {1: "a", 2: "b"}, 2, 1, lambda a, b: float("nan"), Draws(0, 0))
        with self.assertRaises(ValueError):
            SHAW.shaw_removal([[1, 1]], {1: "a"}, 1, 1, lambda a, b: 0, Draws(0))
        with self.assertRaises(ValueError):
            SHAW.shaw_removal([[1]], {1: "a"}, 1, 0.5, lambda a, b: 0, Draws(0))


if __name__ == "__main__":
    unittest.main()
