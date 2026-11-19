"""用独立穷举核对 ALG-001 硬容量 Split 的输出。"""

import importlib.util
from pathlib import Path
import random
import unittest


SOURCE = Path(__file__).resolve().with_name("split.py")
SPEC = importlib.util.spec_from_file_location("alg_001_split", SOURCE)
SPLIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SPLIT)


def exhaustive(demands, capacity, from_depot, to_depot, between):
    """枚举所有分段，直接计算每条路线的负载和距离。"""
    n = len(demands)
    if n == 0:
        return 0
    best = None
    for mask in range(1 << (n - 1)):
        boundaries = [0] + [i for i in range(1, n) if mask & (1 << (i - 1))] + [n]
        if any(sum(demands[a:b]) > capacity for a, b in zip(boundaries, boundaries[1:])):
            continue
        cost = sum(
            from_depot[a] + sum(between[a:b - 1]) + to_depot[b - 1]
            for a, b in zip(boundaries, boundaries[1:])
        )
        if best is None or cost < best:
            best = cost
    return best


class SplitTests(unittest.TestCase):
    def test_known_routes_and_empty_input(self):
        result = SPLIT.split_hard_capacity([3, 2, 4], 5, [1, 2, 3], [1, 2, 3], [1, 1])
        self.assertEqual(result, (10, [(0, 2), (2, 3)]))
        self.assertEqual(SPLIT.split_hard_capacity([], 0, [], [], []), (0, []))

    def test_infeasible_and_zero_demands(self):
        self.assertIsNone(SPLIT.split_hard_capacity([2, 6], 5, [1, 1], [1, 1], [1]))
        self.assertEqual(
            SPLIT.split_hard_capacity([0, 0], 0, [1, 100], [100, 1], [0]),
            (2, [(0, 2)]),
        )

    def test_against_all_segmentations(self):
        rng = random.Random(20261112)
        for n in range(1, 9):
            for _ in range(60):
                demands = [rng.randrange(0, 7) for _ in range(n)]
                capacity = rng.randrange(0, 13)
                from_depot = [rng.randrange(0, 20) for _ in range(n)]
                to_depot = [rng.randrange(0, 20) for _ in range(n)]
                between = [rng.randrange(0, 20) for _ in range(n - 1)]
                expected = exhaustive(demands, capacity, from_depot, to_depot, between)
                result = SPLIT.split_hard_capacity(
                    demands, capacity, from_depot, to_depot, between
                )
                with self.subTest(n=n, demands=demands, capacity=capacity):
                    self.assertEqual(None if result is None else result[0], expected)
                    if result is not None:
                        _, routes = result
                        self.assertEqual(routes[0][0], 0)
                        self.assertEqual(routes[-1][1], n)
                        self.assertTrue(all(a < b for a, b in routes))
                        self.assertTrue(all(x[1] == y[0] for x, y in zip(routes, routes[1:])))
                        self.assertTrue(all(sum(demands[a:b]) <= capacity for a, b in routes))
                        cost = sum(
                            from_depot[a] + sum(between[a:b - 1]) + to_depot[b - 1]
                            for a, b in routes
                        )
                        self.assertEqual(cost, result[0])

    def test_invalid_inputs(self):
        cases = [
            ([1], 1, [], [1], []),
            ([1], -1, [1], [1], []),
            ([-1], 1, [1], [1], []),
            ([1], 1, [float("nan")], [1], []),
            ([1], 1, [1], [float("inf")], []),
            ([1, 1], 1, [1, 1], [1, 1], [-1]),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                SPLIT.split_hard_capacity(*args)

    def test_float_overflow_is_not_reported_as_infeasibility(self):
        with self.assertRaises(OverflowError):
            SPLIT.split_hard_capacity([1], 1, [1e308], [1e308], [])

    def test_float_load_does_not_disappear_in_prefix_subtraction(self):
        self.assertEqual(
            SPLIT.split_hard_capacity([1e16, 1.0], 1e16, [1, 100], [100, 1], [0]),
            (202, [(0, 1), (1, 2)]),
        )

    def test_float_distance_does_not_disappear_in_prefix_subtraction(self):
        self.assertEqual(
            SPLIT.split_hard_capacity([1, 1, 1], 2, [10, 10, 10], [10, 10, 10], [1e16, 1.0]),
            (41.0, [(0, 1), (1, 3)]),
        )


if __name__ == "__main__":
    unittest.main()
