"""与逐客户、逐插入位置穷举比较 SWAP*。"""

import importlib.util
from pathlib import Path
import random
import unittest


SOURCE = Path(__file__).resolve().with_name("swap_star.py")
SPEC = importlib.util.spec_from_file_location("alg_002_swap_star", SOURCE)
SWAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SWAP)


def objective(route, matrix, demand, capacity, penalty):
    nodes = [0, *route, 0]
    distance = sum(matrix[u][v] for u, v in zip(nodes, nodes[1:]))
    return distance + (penalty or 0) * max(sum(demand[v] for v in route) - capacity, 0)


def exhaustive(a, b, matrix, demand, capacity, penalty):
    old = objective(a, matrix, demand, capacity, penalty) + objective(b, matrix, demand, capacity, penalty)
    best = 0
    for ia, u in enumerate(a):
        for ib, v in enumerate(b):
            rest_a = a[:ia] + a[ia + 1:]
            rest_b = b[:ib] + b[ib + 1:]
            for pa in range(len(rest_a) + 1):
                next_a = rest_a[:pa] + [v] + rest_a[pa:]
                for pb in range(len(rest_b) + 1):
                    next_b = rest_b[:pb] + [u] + rest_b[pb:]
                    if penalty is None and (sum(demand[x] for x in next_a) > capacity or
                                            sum(demand[x] for x in next_b) > capacity):
                        continue
                    delta = (objective(next_a, matrix, demand, capacity, penalty) +
                             objective(next_b, matrix, demand, capacity, penalty) - old)
                    best = min(best, delta)
    return best


class SwapStarTests(unittest.TestCase):
    def test_hand_computed_pair(self):
        coords = [0, 1, 100, 2, 99]
        matrix = [[abs(x - y) for y in coords] for x in coords]
        a, b = [1, 2], [3, 4]
        result = SWAP.swap_star_pair(a, b, matrix, [0, 1, 1, 1, 1], 2)
        self.assertIsNotNone(result)
        self.assertEqual(result[2], -194)
        self.assertEqual(sorted(result[0] + result[1]), [1, 2, 3, 4])
        self.assertEqual((a, b), ([1, 2], [3, 4]))

    def test_against_exhaustive_pair_search(self):
        rng = random.Random(20261112)
        for size_a in range(1, 4):
            for size_b in range(1, 4):
                n = size_a + size_b + 1
                for _ in range(20):
                    matrix = [[0 if i == j else rng.randrange(1, 25) for j in range(n)] for i in range(n)]
                    demand = [0] + [rng.randrange(1, 5) for _ in range(n - 1)]
                    a, b = list(range(1, size_a + 1)), list(range(size_a + 1, n))
                    for penalty in (None, 3):
                        cap = max(sum(demand[x] for x in a), sum(demand[x] for x in b)) if penalty is None else 4
                        expected = exhaustive(a, b, matrix, demand, cap, penalty)
                        result = SWAP.swap_star_pair(a, b, matrix, demand, cap, penalty)
                        with self.subTest(a=a, b=b, cap=cap, penalty=penalty):
                            self.assertEqual(0 if result is None else result[2], expected)
                            if result is not None:
                                new_a, new_b, delta = result
                                self.assertEqual(sorted(new_a + new_b), sorted(a + b))
                                observed = (objective(new_a, matrix, demand, cap, penalty) +
                                            objective(new_b, matrix, demand, cap, penalty) -
                                            objective(a, matrix, demand, cap, penalty) -
                                            objective(b, matrix, demand, cap, penalty))
                                self.assertEqual(observed, delta)

    def test_empty_and_invalid_routes(self):
        matrix = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
        self.assertIsNone(SWAP.swap_star_pair([], [1], matrix, [0, 1, 1], 2))
        with self.assertRaises(ValueError):
            SWAP.swap_star_pair([1], [1], matrix, [0, 1, 1], 2)
        with self.assertRaises(ValueError):
            SWAP.swap_star_pair([1], [2], matrix, [0, 2, 1], 1)
        with self.assertRaises(ValueError):
            SWAP.swap_star_pair([1], [2], [[1, 1, 1], [1, 0, 1], [1, 1, 0]], [0, 1, 1], 2)


if __name__ == "__main__":
    unittest.main()
