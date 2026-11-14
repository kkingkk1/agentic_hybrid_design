import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("matching", Path(__file__).with_name("hopcroft_karp.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_all_assignments(self):
        rng = Random(1033)
        for _ in range(100):
            left = 4; right = 4; edges = [(u, v) for u in range(left) for v in range(right) if rng.randrange(2)]
            best = 0
            for a in product(range(-1, right), repeat=left):
                picked = [x for x in a if x >= 0]
                if len(picked) == len(set(picked)) and all(v == -1 or (u, v) in edges for u, v in enumerate(a)):
                    best = max(best, len(picked))
            matching = m.hopcroft_karp(left, right, edges)
            self.assertEqual(len(matching), best)
            self.assertTrue(all(pair in edges for pair in matching))
            self.assertEqual(len({u for u, v in matching}), len(matching))
            self.assertEqual(len({v for u, v in matching}), len(matching))

    def test_empty_and_invalid(self):
        self.assertEqual(m.hopcroft_karp(0, 0, []), [])
        with self.assertRaises(ValueError):
            m.hopcroft_karp(1, 1, [(0, 1)])
