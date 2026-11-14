import importlib.util
from itertools import permutations
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("tsp_bb", Path(__file__).with_name("tsp_branch_bound.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_exhaustive_directed_tsp(self):
        rng = Random(1014)
        for n in range(2, 8):
            for _ in range(12):
                d = [[0 if i == j else rng.randrange(20) for j in range(n)] for i in range(n)]
                expected = min(sum(d[p[i]][p[i + 1]] for i in range(n))
                               for p in ((0, *order, 0) for order in permutations(range(1, n))))
                value, path = m.tsp_branch_bound(d)
                self.assertEqual(value, expected)
                self.assertEqual(value, sum(d[path[i]][path[i + 1]] for i in range(n)))

    def test_single_and_invalid(self):
        self.assertEqual(m.tsp_branch_bound([[0]]), (0, [0, 0]))
        with self.assertRaises(ValueError):
            m.tsp_branch_bound([[0, -1], [1, 0]])
