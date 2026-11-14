import importlib.util
from pathlib import Path
from random import Random
import unittest

spec = importlib.util.spec_from_file_location("knapsack_dp", Path(__file__).with_name("knapsack_dp.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Checks(unittest.TestCase):
    def test_against_subsets(self):
        rng = Random(1011)
        for n in range(9):
            for _ in range(20):
                w = [rng.randrange(5) for _ in range(n)]
                v = [rng.randrange(10) for _ in range(n)]
                cap = rng.randrange(10)
                optimum = max(sum(v[i] for i in range(n) if mask >> i & 1)
                              for mask in range(1 << n)
                              if sum(w[i] for i in range(n) if mask >> i & 1) <= cap)
                result, chosen = module.knapsack_dp(w, v, cap)
                self.assertEqual(result, optimum)
                self.assertLessEqual(sum(w[i] for i in chosen), cap)
                self.assertEqual(sum(v[i] for i in chosen), result)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            module.knapsack_dp([1], [2], -1)
