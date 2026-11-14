import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("knapsack_bb", Path(__file__).with_name("knapsack_branch_bound.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_exhaustive_knapsack(self):
        rng = Random(1015)
        for n in range(10):
            for _ in range(20):
                w = [rng.randrange(1, 8) for _ in range(n)]; v = [rng.randrange(12) for _ in range(n)]; cap = rng.randrange(16)
                expected = max(sum(v[i] for i in range(n) if mask >> i & 1) for mask in range(1 << n)
                               if sum(w[i] for i in range(n) if mask >> i & 1) <= cap)
                value, selected = m.knapsack_branch_bound(w, v, cap)
                self.assertEqual(value, expected)
                self.assertLessEqual(sum(w[i] for i in selected), cap)
                self.assertEqual(sum(v[i] for i in selected), value)

    def test_invalid_weight(self):
        with self.assertRaises(ValueError):
            m.knapsack_branch_bound([0], [1], 2)
