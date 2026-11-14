import importlib.util
from pathlib import Path
import unittest

s = importlib.util.spec_from_file_location("beam", Path(__file__).with_name("beam_search.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_width_can_prune_solution(self):
        graph = {0: [1, 2], 1: [3], 2: [4]}
        h = {1: 0, 2: 1, 3: 0, 4: 0}
        self.assertIsNone(m.beam_search(graph, 0, 4, 1, 2, h.__getitem__))
        self.assertEqual(m.beam_search(graph, 0, 4, 2, 2, h.__getitem__), [0, 2, 4])

    def test_depth_cycle_and_invalid(self):
        self.assertEqual(m.beam_search({0: [0]}, 0, 0, 1, 0, lambda v: 0), [0])
        with self.assertRaises(ValueError):
            m.beam_search({}, 0, 1, 0, 5, lambda v: 0)
