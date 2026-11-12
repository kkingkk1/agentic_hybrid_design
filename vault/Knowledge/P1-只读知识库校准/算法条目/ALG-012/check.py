import importlib.util
from pathlib import Path
from random import Random
import unittest

spec = importlib.util.spec_from_file_location("weighted_intervals", Path(__file__).with_name("weighted_intervals.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Checks(unittest.TestCase):
    def test_against_subsets(self):
        rng = Random(1012)
        for n in range(9):
            for _ in range(15):
                jobs = [(a := rng.randrange(9), a + rng.randrange(1, 5), rng.randrange(-2, 9)) for _ in range(n)]
                best = 0
                for mask in range(1 << n):
                    chosen = sorted((jobs[i] for i in range(n) if mask >> i & 1))
                    if all(chosen[i][1] <= chosen[i + 1][0] for i in range(len(chosen) - 1)):
                        best = max(best, sum(x[2] for x in chosen))
                value, chosen = module.weighted_intervals(jobs)
                self.assertEqual(value, best)
                self.assertEqual(sum(jobs[i][2] for i in chosen), value)

    def test_touching_and_invalid(self):
        self.assertEqual(module.weighted_intervals([(0, 1, 1), (1, 2, 2)]), (3, [0, 1]))
        with self.assertRaises(ValueError):
            module.weighted_intervals([(1, 1, 2)])
