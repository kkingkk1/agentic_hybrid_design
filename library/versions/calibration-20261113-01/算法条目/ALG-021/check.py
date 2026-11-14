import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("table", Path(__file__).with_name("table_gac.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_tuple_support(self):
        rng = Random(1021); tuples = list(product(range(3), repeat=3))
        for _ in range(100):
            rows = [x for x in tuples if rng.randrange(3) == 0]
            domains = [{v for v in range(3) if rng.randrange(2)} for _ in range(3)]
            valid = [x for x in rows if all(x[i] in domains[i] for i in range(3))]
            expected = [{x[i] for x in valid} for i in range(3)] if valid else None
            self.assertEqual(m.table_gac(domains, rows), expected)

    def test_empty_and_bad_arity(self):
        self.assertEqual(m.table_gac([], [()]), [])
        with self.assertRaises(ValueError):
            m.table_gac([{1}], [(1, 2)])
