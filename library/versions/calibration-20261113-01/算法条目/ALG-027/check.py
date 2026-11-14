import importlib.util
from itertools import product
from pathlib import Path
from random import Random
import unittest

s = importlib.util.spec_from_file_location("cover", Path(__file__).with_name("cover_cut.py"))
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


class Checks(unittest.TestCase):
    def test_violated_cuts_valid_for_binary_solutions(self):
        rng = Random(1027)
        for _ in range(100):
            n = 6; w = [rng.randrange(1, 7) for _ in range(n)]; cap = rng.randrange(4, 15)
            x = [rng.randrange(3) / 2 for _ in range(n)]
            cover = m.violated_cover(w, cap, x)
            exists = any(sum(w[i] for i in range(n) if mask >> i & 1) > cap and
                         sum(x[i] for i in range(n) if mask >> i & 1) > mask.bit_count() - 1
                         for mask in range(1, 1 << n))
            self.assertEqual(cover is not None, exists)
            if cover is not None:
                self.assertGreater(sum(w[i] for i in cover), cap)
                self.assertGreater(sum(x[i] for i in cover), len(cover) - 1)
                for y in product((0, 1), repeat=n):
                    if sum(a * b for a, b in zip(w, y)) <= cap:
                        self.assertLessEqual(sum(y[i] for i in cover), len(cover) - 1)

    def test_not_violated(self):
        self.assertIsNone(m.violated_cover([2, 2], 3, [0.5, 0.5]))
