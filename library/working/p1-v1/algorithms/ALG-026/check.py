from fractions import Fraction
import importlib.util
from itertools import combinations
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("simplex", Path(__file__).with_name("primal_simplex.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_two_dimensional_vertices(self):
        rng = Random(1026)
        for _ in range(100):
            a = [[1, 0], [0, 1]] + [[rng.randrange(5), rng.randrange(5)] for _ in range(3)]
            b = [rng.randrange(1, 9) for _ in a]; c = [rng.randrange(-2, 6), rng.randrange(-2, 6)]
            lines = list(zip(a, b)) + [([-1, 0], 0), ([0, -1], 0)]
            candidates = []
            for (u, r), (v, t) in combinations(lines, 2):
                det = u[0] * v[1] - u[1] * v[0]
                if not det: continue
                x = Fraction(r * v[1] - u[1] * t, det); y = Fraction(u[0] * t - r * v[0], det)
                if x >= 0 and y >= 0 and all(row[0] * x + row[1] * y <= bound for row, bound in zip(a, b)):
                    candidates.append(c[0] * x + c[1] * y)
            status, value, solution = m.primal_simplex(a, b, c)
            self.assertEqual(status, "optimal"); self.assertEqual(value, max(candidates))
            self.assertEqual(value, c[0] * solution[0] + c[1] * solution[1])

    def test_unbounded_and_invalid(self):
        self.assertEqual(m.primal_simplex([[-1]], [0], [1]), ("unbounded", None, None))
        with self.assertRaises(ValueError):
            m.primal_simplex([[1]], [-1], [1])
