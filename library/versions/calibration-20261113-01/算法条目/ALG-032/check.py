import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("maxflow", Path(__file__).with_name("edmonds_karp.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_all_cuts(self):
        rng = Random(1032)
        for _ in range(100):
            n = 6; edges = [(i, j, rng.randrange(5)) for i in range(n) for j in range(n) if i != j and rng.randrange(4) == 0]
            cuts = []
            for mask in range(1 << n):
                if not mask & 1 or mask >> (n - 1) & 1: continue
                cuts.append(sum(c for u, v, c in edges if mask >> u & 1 and not mask >> v & 1))
            value, side = m.edmonds_karp(n, edges, 0, n - 1)
            self.assertEqual(value, min(cuts))
            self.assertEqual(value, sum(c for u, v, c in edges if u in side and v not in side))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            m.edmonds_karp(2, [(0, 1, -1)], 0, 1)
