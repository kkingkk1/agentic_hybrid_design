"""检查模拟退火概率边界和温度更新。"""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("alg_007_annealing", Path(__file__).with_name("annealing_acceptance.py"))
SA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SA)


class Draw:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def random(self):
        self.calls += 1
        return self.value


class AnnealingTests(unittest.TestCase):
    def test_improvements_and_equal_need_no_random_draw(self):
        rng = Draw(0.99)
        self.assertTrue(SA.annealing_accept(10, 9, 1, rng))
        self.assertTrue(SA.annealing_accept(10, 10, 1, rng))
        self.assertEqual(rng.calls, 0)

    def test_worse_solution_and_extreme_values(self):
        self.assertTrue(SA.annealing_accept(0, 1, 1, Draw(0.36)))
        self.assertFalse(SA.annealing_accept(0, 1, 1, Draw(0.37)))
        self.assertTrue(SA.annealing_accept(0, 10**400, 1, Draw(0)))
        self.assertFalse(SA.annealing_accept(0, 10**400, 1, Draw(0.5)))

    def test_cooling_and_invalid_inputs(self):
        self.assertEqual(SA.cool_temperature(10, 0.5), 5.0)
        with self.assertRaises(ValueError):
            SA.cool_temperature(5e-324, 0.5)
        for temp, rate in [(0, 0.5), (1, 0), (1, 1), (1, float("nan"))]:
            with self.subTest(temp=temp, rate=rate), self.assertRaises(ValueError):
                SA.cool_temperature(temp, rate)
        with self.assertRaises(ValueError):
            SA.annealing_accept(1, 2, 0, Draw(0))
        with self.assertRaises(ValueError):
            SA.annealing_accept(1, 2, 1, Draw(1))
        with self.assertRaises(ValueError):
            SA.annealing_accept(float("inf"), 1, 1, Draw(0))


if __name__ == "__main__":
    unittest.main()
