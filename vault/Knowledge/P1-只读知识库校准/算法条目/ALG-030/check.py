import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("bellman", Path(__file__).with_name("bellman_ford.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_negative_edges_against_dag_paths(self):
        rng = Random(1030)
        for _ in range(100):
            n = 7; edges = [(i, j, rng.randrange(-6, 8)) for i in range(n) for j in range(i + 1, n) if rng.randrange(3) == 0]
            paths = {0: [0]}
            for v in range(1, n):
                paths[v] = [x + w for u, z, w in edges if z == v for x in paths.get(u, [])]
            self.assertEqual(m.bellman_ford(n, edges, 0)[0], [min(paths[i]) if paths[i] else None for i in range(n)])

    def test_reachable_versus_unreachable_cycle(self):
        self.assertEqual(m.bellman_ford(4, [(2, 3, -1), (3, 2, 0)], 0)[0], [0, None, None, None])
        with self.assertRaises(ValueError):
            m.bellman_ford(2, [(0, 1, -1), (1, 0, 0)], 0)
