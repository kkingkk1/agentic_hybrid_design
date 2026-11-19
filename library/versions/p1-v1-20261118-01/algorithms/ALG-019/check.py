import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("ac3", Path(__file__).with_name("ac3.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_random_networks_preserve_solutions_and_are_arc_consistent(self):
        rng = Random(1019)
        for _ in range(100):
            domains = {i: {0, 1, 2} for i in range(4)}
            constraints = [(i, j, {(a, b) for a in domains[i] for b in domains[j] if rng.randrange(2)})
                           for i in range(4) for j in range(i + 1, 4) if rng.randrange(2)]
            solutions = [row for row in product(range(3), repeat=4)
                         if all((row[i], row[j]) in pairs for i, j, pairs in constraints)]
            filtered = m.ac3(domains, constraints)
            if solutions:
                self.assertIsNotNone(filtered)
                self.assertTrue(all(row[i] in filtered[i] for row in solutions for i in domains))
            if filtered is not None:
                for i, j, pairs in constraints:
                    self.assertTrue(all(any((a, b) in pairs for b in filtered[j]) for a in filtered[i]))
                    self.assertTrue(all(any((a, b) in pairs for a in filtered[i]) for b in filtered[j]))

    def test_propagation_and_inputs(self):
        domains = {"a": {1, 2}, "b": {1, 2}, "c": {2}}
        neq = {(1, 2), (2, 1)}
        self.assertEqual(m.ac3(domains, [("a", "b", neq), ("b", "c", neq)]), {"a": {2}, "b": {1}, "c": {2}})
        self.assertEqual(domains["a"], {1, 2})

    def test_empty_and_arc_consistency_not_global(self):
        neq = {(1, 2), (2, 1)}
        self.assertIsNone(m.ac3({0: {1}, 1: {1}}, [(0, 1, neq)]))
        d = {i: {1, 2} for i in range(3)}
        self.assertEqual(m.ac3(d, [(0, 1, neq), (1, 2, neq), (0, 2, neq)]), d)

    def test_multiple_constraints_in_opposite_directions(self):
        domains = {0: {0, 1}, 1: {0, 1}}
        constraints = [(0, 1, {(0, 0), (1, 1)}), (1, 0, {(0, 0), (0, 1)})]
        self.assertEqual(m.ac3(domains, constraints), {0: {0}, 1: {0}})
