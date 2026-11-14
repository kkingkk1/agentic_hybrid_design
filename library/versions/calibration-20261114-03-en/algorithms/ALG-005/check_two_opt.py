"""检查对称 TSP 的 2-Opt 改进及局部最优条件。"""

import importlib.util
from pathlib import Path
import random
import unittest


SOURCE = Path(__file__).resolve().with_name("two_opt.py")
SPEC = importlib.util.spec_from_file_location("alg_005_two_opt", SOURCE)
TWO_OPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TWO_OPT)


def length(tour, matrix):
    return sum(matrix[tour[i]][tour[(i + 1) % len(tour)]] for i in range(len(tour)))


class TwoOptTests(unittest.TestCase):
    def test_crossed_square(self):
        matrix = [[0, 1, 2, 1], [1, 0, 1, 2], [2, 1, 0, 1], [1, 2, 1, 0]]
        tour = [0, 2, 1, 3]
        cost, result = TWO_OPT.two_opt(tour, matrix)
        self.assertEqual(cost, 4)
        self.assertEqual(length(result, matrix), cost)
        self.assertEqual(tour, [0, 2, 1, 3])

    def test_random_tours_are_locally_optimal(self):
        rng = random.Random(20261112)
        for n in range(4, 10):
            for _ in range(25):
                matrix = [[0] * n for _ in range(n)]
                for i in range(n):
                    for j in range(i):
                        matrix[i][j] = matrix[j][i] = rng.randrange(1, 30)
                tour = list(range(n))
                rng.shuffle(tour)
                cost, result = TWO_OPT.two_opt(tour, matrix)
                with self.subTest(n=n, tour=tour):
                    self.assertEqual(set(result), set(range(n)))
                    self.assertEqual(result[0], tour[0])
                    self.assertEqual(cost, length(result, matrix))
                    self.assertLessEqual(cost, length(tour, matrix))
                    for i in range(n):
                        for j in range(i + 2, n):
                            if i == 0 and j == n - 1:
                                continue
                            candidate = result[:i + 1] + list(reversed(result[i + 1:j + 1])) + result[j + 1:]
                            self.assertGreaterEqual(length(candidate, matrix), cost)

    def test_small_and_invalid_inputs(self):
        self.assertEqual(TWO_OPT.two_opt([], []), (0, []))
        self.assertEqual(TWO_OPT.two_opt([0], [[0]]), (0, [0]))
        cases = [
            ([0, 0], [[0, 1], [1, 0]]),
            ([0, 1], [[0, 1], [2, 0]]),
            ([0, 1], [[0, -1], [-1, 0]]),
            ([0, 1], [[0, float("nan")], [float("nan"), 0]]),
            ([0], [[1]]),
        ]
        for tour, matrix in cases:
            with self.subTest(tour=tour, matrix=matrix), self.assertRaises(ValueError):
                TWO_OPT.two_opt(tour, matrix)


if __name__ == "__main__":
    unittest.main()
