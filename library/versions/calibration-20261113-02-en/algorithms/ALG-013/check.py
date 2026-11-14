import importlib.util
from pathlib import Path
from random import Random
import unittest

spec = importlib.util.spec_from_file_location("dag_paths", Path(__file__).with_name("dag_paths.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Checks(unittest.TestCase):
    def test_against_path_enumeration(self):
        rng = Random(1013)
        for n in range(2, 9):
            for _ in range(20):
                edges = [(i, j, rng.randrange(-5, 9)) for i in range(n) for j in range(i + 1, n) if rng.randrange(3) == 0]
                options = {0: [0]}
                for v in range(1, n):
                    options[v] = [cost + w for u, target, w in edges if target == v for cost in options.get(u, [])]
                actual, _ = module.dag_shortest_paths(n, edges, 0)
                self.assertEqual(actual, [min(options[i]) if options[i] else None for i in range(n)])

    def test_negative_and_cycle(self):
        self.assertEqual(module.dag_shortest_paths(3, [(0, 1, -2)], 0)[0], [0, -2, None])
        with self.assertRaises(ValueError):
            module.dag_shortest_paths(2, [(0, 1, 1), (1, 0, 1)], 0)
