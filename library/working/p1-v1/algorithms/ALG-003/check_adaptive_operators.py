"""检查算子抽样、计分和分段更新。"""

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().with_name("adaptive_operators.py")
SPEC = importlib.util.spec_from_file_location("alg_003_adaptive", SOURCE)
ADAPTIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTIVE)


class Draw:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class AdaptiveOperatorTests(unittest.TestCase):
    def test_roulette_boundaries_and_zero_weight(self):
        self.assertEqual(ADAPTIVE.choose_operator([0, 1, 3], Draw(0)), 1)
        self.assertEqual(ADAPTIVE.choose_operator([0, 1, 3], Draw(0.249)), 1)
        self.assertEqual(ADAPTIVE.choose_operator([0, 1, 3], Draw(0.25)), 2)
        self.assertEqual(ADAPTIVE.choose_operator([0, 1, 3], Draw(0.999)), 2)

    def test_three_rewards_and_priority(self):
        score = ADAPTIVE.score_outcome
        rewards = [9, 4, 1]
        self.assertEqual(score(4, 8, 5, True, False, rewards), 9)
        self.assertEqual(score(6, 8, 5, True, False, rewards), 4)
        self.assertEqual(score(9, 8, 5, True, False, rewards), 1)
        self.assertEqual(score(9, 8, 5, False, False, rewards), 0)
        self.assertEqual(score(6, 8, 5, True, True, rewards), 0)
        self.assertEqual(score(8, 8, 5, True, False, rewards), 0)

    def test_segment_update_and_unused_operator(self):
        actual = ADAPTIVE.update_weights([10, 4, 3], [6, 0, 0], [2, 1, 0], 0.5)
        self.assertEqual(actual, [6.5, 2.0, 3.0])
        self.assertEqual(ADAPTIVE.update_weights([3], [10], [2], 0), [3.0])
        self.assertEqual(ADAPTIVE.update_weights([3], [10], [2], 1), [5.0])
        self.assertAlmostEqual(ADAPTIVE.update_weights([0.3], [0.1], [2], 0.2)[0], 0.25)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            ADAPTIVE.choose_operator([0, 0], Draw(0.5))
        with self.assertRaises(ValueError):
            ADAPTIVE.choose_operator([1], Draw(1.0))
        with self.assertRaises(ValueError):
            ADAPTIVE.update_weights([1], [1], [0], 0.5)
        with self.assertRaises(ValueError):
            ADAPTIVE.update_weights([1], [0], [1], 1.1)
        with self.assertRaises(ValueError):
            ADAPTIVE.score_outcome(1, 2, 0, True, False, [1, 2])


if __name__ == "__main__":
    unittest.main()
