import importlib.util
from itertools import combinations
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("kruskal", Path(__file__).with_name("kruskal.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_spanning_tree_enumeration(self):
        rng = Random(1031)
        for _ in range(80):
            n = 5; edges = [(i, j, rng.randrange(-3, 9)) for i in range(n) for j in range(i + 1, n) if rng.randrange(3)]
            weights = []
            for group in combinations(edges, n - 1):
                reached = {0}
                for _ in range(n):
                    for u, v, w in group:
                        if u in reached: reached.add(v)
                        if v in reached: reached.add(u)
                if len(reached) == n: weights.append(sum(e[2] for e in group))
            actual = m.kruskal(n, edges)
            self.assertEqual(None if actual is None else actual[0], min(weights) if weights else None)

    def test_empty_and_disconnected(self):
        self.assertEqual(m.kruskal(0, []), (0, []))
        self.assertIsNone(m.kruskal(2, []))
