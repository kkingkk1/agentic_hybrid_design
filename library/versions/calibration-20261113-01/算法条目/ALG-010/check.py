import importlib.util
from itertools import permutations
from pathlib import Path
from random import Random
import unittest

spec = importlib.util.spec_from_file_location("held_karp", Path(__file__).with_name("held_karp.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Checks(unittest.TestCase):
    def test_against_permutations(self):
        rng = Random(1010)
        for n in range(2, 8):
            for _ in range(12):
                d = [[0 if i == j else rng.randrange(-3, 20) for j in range(n)] for i in range(n)]
                expected = min(sum(d[p[i]][p[i + 1]] for i in range(n))
                               for p in ((0, *order, 0) for order in permutations(range(1, n))))
                cost, path = module.held_karp(d)
                self.assertEqual(cost, expected)
                self.assertEqual(sum(d[path[i]][path[i + 1]] for i in range(n)), cost)
                self.assertEqual(set(path[:-1]), set(range(n)))

    def test_singleton_and_invalid(self):
        self.assertEqual(module.held_karp([[0]]), (0, [0, 0]))
        with self.assertRaises(ValueError):
            module.held_karp([[0, 1], [1, float("nan")]])
