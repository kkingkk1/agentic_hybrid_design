import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("lagrangian", Path(__file__).with_name("lagrangian_knapsack.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_bound_against_subsets(self):
        rng = Random(1025)
        for n in range(9):
            for _ in range(20):
                w = [rng.randrange(6) for _ in range(n)]; v = [rng.randrange(10) for _ in range(n)]; cap = rng.randrange(10)
                exact = max(sum(v[i] for i in range(n) if mask >> i & 1) for mask in range(1 << n)
                            if sum(w[i] for i in range(n) if mask >> i & 1) <= cap)
                bound, selected = m.lagrangian_knapsack(w, v, cap, 0.5)
                self.assertGreaterEqual(bound, exact)
                self.assertEqual(bound, cap / 2 + sum(v[i] - w[i] / 2 for i in selected))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            m.lagrangian_knapsack([1], [2], 3, -1)
