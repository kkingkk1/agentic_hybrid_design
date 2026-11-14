"""检查顺序交叉的区间与排列不变量。"""

import importlib.util
from pathlib import Path
import random
import unittest


SPEC = importlib.util.spec_from_file_location("alg_006_order", Path(__file__).with_name("order_crossover.py"))
OX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OX)


class OrderCrossoverTests(unittest.TestCase):
    def test_hand_computed_and_wrapped_interval(self):
        a, b = [1, 2, 3, 4, 5, 6, 7, 8], [4, 5, 2, 1, 8, 7, 6, 3]
        self.assertEqual(OX.order_crossover(a, b, 2, 4), [1, 8, 3, 4, 5, 7, 6, 2])
        self.assertEqual(OX.order_crossover(a, b, 6, 1), [1, 2, 6, 3, 4, 5, 7, 8])
        self.assertEqual(OX.order_crossover(a, b, 2, 1), a)
        self.assertEqual(a, [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(b, [4, 5, 2, 1, 8, 7, 6, 3])

    def test_random_permutations_preserve_segment_and_relative_order(self):
        rng = random.Random(20261112)
        for n in range(1, 11):
            for _ in range(30):
                a, b = list(range(n)), list(range(n))
                rng.shuffle(a)
                rng.shuffle(b)
                start, end = rng.randrange(n), rng.randrange(n)
                child = OX.order_crossover(a, b, start, end)
                segment = []
                i = start
                while True:
                    segment.append(i)
                    if i == end:
                        break
                    i = (i + 1) % n
                self.assertEqual(sorted(child), list(range(n)))
                self.assertTrue(all(child[i] == a[i] for i in segment))
                outside = [(end + 1 + i) % n for i in range(n) if (end + 1 + i) % n not in segment]
                expected = [b[(end + 1 + i) % n] for i in range(n) if b[(end + 1 + i) % n] not in {a[j] for j in segment}]
                self.assertEqual([child[i] for i in outside], expected)

    def test_invalid_and_none_gene(self):
        self.assertEqual(OX.order_crossover([None, 1], [1, None], 0, 0), [None, 1])
        for a, b, start, end in [([], [], 0, 0), ([1], [2], 0, 0), ([1, 1], [1, 2], 0, 1), ([1], [1], True, 0), ([[1]], [[1]], 0, 0)]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                OX.order_crossover(a, b, start, end)


if __name__ == "__main__":
    unittest.main()
