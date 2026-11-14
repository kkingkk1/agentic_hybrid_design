from fractions import Fraction
import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("fractional", Path(__file__).with_name("fractional_knapsack.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_enumerated_vertices(self):
        rng = Random(1024)
        for n in range(1, 8):
            for _ in range(20):
                w = [rng.randrange(1, 8) for _ in range(n)]; v = [rng.randrange(9) for _ in range(n)]; cap = rng.randrange(15)
                candidates = [Fraction(0)]
                for mask in range(1 << n):
                    used = sum(w[i] for i in range(n) if mask >> i & 1)
                    if used > cap: continue
                    base = sum(v[i] for i in range(n) if mask >> i & 1)
                    candidates.append(Fraction(base))
                    for i in range(n):
                        if not mask >> i & 1:
                            candidates.append(base + Fraction(v[i] * min(w[i], cap - used), w[i]))
                value, selection = m.fractional_knapsack(w, v, cap)
                self.assertEqual(value, max(candidates))
                self.assertLessEqual(sum(w[i] * selection[i] for i in range(n)), cap)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            m.fractional_knapsack([0], [1], 3)
