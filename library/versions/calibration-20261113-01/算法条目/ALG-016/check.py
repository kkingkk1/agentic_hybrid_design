from collections import deque
import importlib.util
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("iddfs", Path(__file__).with_name("iterative_deepening.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_against_bfs(self):
        rng = Random(1016)
        for _ in range(100):
            g = {i: [j for j in range(6) if rng.randrange(4) == 0] for i in range(6)}
            queue = deque([(0, 0)]); seen = {0}; target = None
            while queue:
                v, depth = queue.popleft()
                if v == 5:
                    target = depth; break
                for nxt in g[v]:
                    if nxt not in seen:
                        seen.add(nxt); queue.append((nxt, depth + 1))
            p = m.iterative_deepening(g, 0, 5, 5)
            self.assertEqual(None if p is None else len(p) - 1, target)

    def test_limit_and_cycle(self):
        self.assertIsNone(m.iterative_deepening({0: [1], 1: [0, 2]}, 0, 2, 1))
        self.assertEqual(m.iterative_deepening({}, 0, 0, 0), [0])
