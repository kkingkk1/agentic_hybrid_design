import importlib.util
from itertools import permutations
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("hungarian", Path(__file__).with_name("hungarian.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_enumeration(self):
        rng = Random(1028)
        for n in range(1, 6):
            for cols in range(n, 7):
                for _ in range(8):
                    a = [[rng.randrange(-5, 10) for _ in range(cols)] for _ in range(n)]
                    expected = min(sum(a[i][p[i]] for i in range(n)) for p in permutations(range(cols), n))
                    value, assignment = m.hungarian(a)
                    self.assertEqual(value, expected)
                    self.assertEqual(value, sum(a[i][assignment[i]] for i in range(n)))
                    self.assertEqual(len(set(assignment)), n)

    def test_empty_and_invalid(self):
        self.assertEqual(m.hungarian([]), (0, []))
        with self.assertRaises(ValueError):
            m.hungarian([[1], [2]])
