import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("alldiff", Path(__file__).with_name("all_different_gac.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_assignments(self):
        rng = Random(1022)
        for n in range(5):
            for _ in range(40):
                domains = [{v for v in range(4) if rng.randrange(2)} for _ in range(n)]
                solutions = [x for x in product(*domains) if len(set(x)) == n]
                expected = [{x[i] for x in solutions} for i in range(n)] if solutions else None
                self.assertEqual(m.all_different_gac(domains), expected)

    def test_hall_and_impossible(self):
        self.assertEqual(m.all_different_gac([{1, 2}, {1, 2}, {1, 2, 3}]), [{1, 2}, {1, 2}, {3}])
        self.assertIsNone(m.all_different_gac([{1}, {1}]))
