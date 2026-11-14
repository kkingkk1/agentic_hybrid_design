"""检查高代价移除的动态重算和节点配对。"""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("alg_009_worst", Path(__file__).with_name("worst_removal.py"))
WORST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORST)


class Draws:
    def __init__(self, *values):
        self.values = iter(values)

    def random(self):
        return next(self.values)


class WorstTests(unittest.TestCase):
    def test_marginal_cost_recomputed_after_each_removal(self):
        costs = {("a", "b", "c"): 20, ("b", "c"): 10, ("a", "c"): 15,
                 ("a", "b"): 18, ("c",): 9, ("b",): 2}
        routes = [["a", "b", "c"]]
        mapping = {v: v for v in routes[0]}
        result, removed = WORST.worst_removal(routes, mapping, 2, 2, lambda x: costs[x[0]], Draws(0, 0))
        self.assertEqual(removed, ["a", "c"])
        self.assertEqual(result, [["b"]])
        self.assertEqual(routes, [["a", "b", "c"]])

    def test_pair_removed_and_rank_randomization(self):
        routes = [["ap", "ad", "bp", "bd"]]
        mapping = {"ap": "a", "ad": "a", "bp": "b", "bd": "b"}
        weights = {"ap": 5, "ad": 5, "bp": 1, "bd": 1}
        objective = lambda rs: sum(weights[n] for route in rs for n in route)
        result, removed = WORST.worst_removal(routes, mapping, 1, 1, objective, Draws(0.9))
        self.assertEqual(removed, ["b"])
        self.assertEqual(result, [["ap", "ad"]])
        _, selected = WORST.worst_removal(routes, mapping, 1, 10**400, objective, Draws(0.9))
        self.assertEqual(selected, ["a"])

    def test_zero_and_invalid_inputs(self):
        self.assertEqual(WORST.worst_removal([[]], {}, 0, 1, lambda x: 0, Draws()), ([[]], []))
        with self.assertRaises(ValueError):
            WORST.worst_removal([[1], [2]], {1: "a", 2: "a"}, 1, 1, lambda x: 0, Draws(0))
        with self.assertRaises(ValueError):
            WORST.worst_removal([[1]], {1: "a"}, 2, 1, lambda x: 0, Draws(0))
        with self.assertRaises(ValueError):
            WORST.worst_removal([[1]], {1: "a"}, 1, 1, lambda x: float("inf"), Draws(0))
        with self.assertRaises(ValueError):
            WORST.worst_removal([[1]], {1: "a"}, 1, 0.5, lambda x: 0, Draws(0))


if __name__ == "__main__":
    unittest.main()
