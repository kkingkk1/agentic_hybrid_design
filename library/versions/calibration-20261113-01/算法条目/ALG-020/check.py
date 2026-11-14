import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("csp", Path(__file__).with_name("csp_forward_checking.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_all_assignments(self):
        rng = Random(1020)
        for _ in range(100):
            d = {i: [0, 1, 2] for i in range(4)}
            constraints = [(i, j, {(a, b) for a in d[i] for b in d[j] if rng.randrange(2)})
                           for i in range(4) for j in range(i + 1, 4) if rng.randrange(2)]
            valid = [x for x in product(range(3), repeat=4) if all((x[i], x[j]) in pairs for i, j, pairs in constraints)]
            result = m.solve_csp(d, constraints)
            self.assertEqual(result is None, not valid)
            if result is not None:
                self.assertTrue(all((result[i], result[j]) in pairs for i, j, pairs in constraints))

    def test_empty_problem_and_unsat(self):
        self.assertEqual(m.solve_csp({}, []), {})
        self.assertIsNone(m.solve_csp({0: [1], 1: [1]}, [(0, 1, {(1, 2)})]))

    def test_multiple_constraints_in_opposite_directions(self):
        constraints = [(0, 1, {(0, 0), (1, 1)}), (1, 0, {(0, 0), (0, 1)})]
        self.assertEqual(m.solve_csp({0: [0, 1], 1: [0, 1]}, constraints), {0: 0, 1: 0})
