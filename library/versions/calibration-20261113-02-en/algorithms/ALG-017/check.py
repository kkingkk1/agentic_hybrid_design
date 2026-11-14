import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("astar", Path(__file__).with_name("astar_tree.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_path_enumeration(self):
        rng = Random(1017)
        for _ in range(80):
            g = {i: [(j, rng.randrange(8)) for j in range(6) if i != j and rng.randrange(4) == 0] for i in range(6)}
            costs = []
            def visit(node, path, cost):
                if node == 5:
                    costs.append(cost); return
                for nxt, weight in g[node]:
                    if nxt not in path:
                        visit(nxt, path | {nxt}, cost + weight)
            visit(0, {0}, 0)
            result = m.astar_tree(g, 0, 5, lambda node: 0)
            self.assertEqual(None if result is None else result[0], min(costs) if costs else None)

    def test_heuristic_and_invalid(self):
        g = {0: [(1, 2), (2, 1)], 1: [(3, 2)], 2: [(3, 5)]}
        self.assertEqual(m.astar_tree(g, 0, 3, lambda x: {0: 4, 1: 2, 2: 5, 3: 0}[x]), (4, [0, 1, 3]))
        with self.assertRaises(ValueError):
            m.astar_tree(g, 0, 3, lambda x: 1)
