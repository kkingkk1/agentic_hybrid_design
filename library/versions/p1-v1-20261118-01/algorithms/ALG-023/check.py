import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("sum_gac", Path(__file__).with_name("sum_gac.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_assignments(self):
        rng = Random(1023)
        for n in range(5):
            for _ in range(40):
                domains = [{v for v in range(-2, 4) if rng.randrange(2)} for _ in range(n)]
                target = rng.randrange(-5, 8)
                valid = [row for row in product(*domains) if sum(row) == target]
                expected = [{row[i] for row in valid} for i in range(n)] if valid else None
                self.assertEqual(m.sum_equals_gac(domains, target), expected)

    def test_holes_and_invalid(self):
        self.assertEqual(m.sum_equals_gac([{0, 2}, {0, 2}, {1, 3}], 1), [{0}, {0}, {1}])
        with self.assertRaises(ValueError):
            m.sum_equals_gac([{0, 0.5}], 1)
