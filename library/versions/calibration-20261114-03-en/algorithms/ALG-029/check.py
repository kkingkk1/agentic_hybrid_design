import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("dijkstra", Path(__file__).with_name("dijkstra.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_floyd_warshall(self):
        rng = Random(1029)
        for _ in range(80):
            n = 6; edges = [(i, j, rng.randrange(10)) for i in range(n) for j in range(n) if i != j and rng.randrange(4) == 0]
            d = [[None] * n for _ in range(n)]
            for i in range(n): d[i][i] = 0
            for u, v, w in edges: d[u][v] = w
            for k in range(n):
                for i in range(n):
                    for j in range(n):
                        if d[i][k] is not None and d[k][j] is not None:
                            candidate = d[i][k] + d[k][j]
                            if d[i][j] is None or candidate < d[i][j]: d[i][j] = candidate
            self.assertEqual(m.dijkstra(n, edges, 0)[0], d[0])

    def test_rejects_negative_even_unreachable(self):
        with self.assertRaises(ValueError):
            m.dijkstra(3, [(1, 2, -1)], 0)
