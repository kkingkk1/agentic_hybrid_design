"""检查 Regret-k 的路线比较、平局和请求保留。"""

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().with_name("regret_k.py")
SPEC = importlib.util.spec_from_file_location("alg_004_regret", SOURCE)
REGRET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REGRET)


class RegretKTests(unittest.TestCase):
    def test_regret_compares_different_routes(self):
        costs = {("r0", "a"): 1, ("r1", "a"): 11,
                 ("r0", "b"): 0, ("r1", "b"): 2}

        def insert(route, request):
            return costs[(route[0], request)], [*route, request]

        routes = [["r0"], ["r1"]]
        result, remaining = REGRET.regret_k_insert(routes, ["a", "b"], 2, insert)
        self.assertEqual(result, [["r0", "a", "b"], ["r1"]])
        self.assertEqual(remaining, [])
        self.assertEqual(routes, [["r0"], ["r1"]])

    def test_few_routes_before_regret_and_tie_by_cost(self):
        def insert(route, request):
            if request in ("expensive", "cheap") and route[0] == "r1":
                return None
            cost = {"expensive": 8, "cheap": 2, "flexible": 0}[request]
            if request == "flexible" and route[0] == "r1":
                cost = 100
            return cost, [*route, request]

        result, remaining = REGRET.regret_k_insert(
            [["r0"], ["r1"]], ["expensive", "flexible", "cheap"], 2, insert
        )
        self.assertEqual(result[0], ["r0", "cheap", "expensive", "flexible"])
        self.assertEqual(remaining, [])

    def test_uninsertable_requests_stay_in_bank(self):
        def insert(route, request):
            return None if request == "blocked" else (1, [*route, request])

        result, remaining = REGRET.regret_k_insert([["r0"]], ["blocked", "ok"], 1, insert)
        self.assertEqual(result, [["r0", "ok"]])
        self.assertEqual(remaining, ["blocked"])
        self.assertEqual(REGRET.regret_k_insert([], ["a"], 2, insert), ([], ["a"]))

    def test_pickup_delivery_callback_checks_capacity_and_time_windows(self):
        pairs = {"a": (1, 2), "b": (3, 4), "blocked": (5, 6)}
        position = [0, 1, 2, 3, 4, 8, 9]
        latest = [30, 20, 20, 20, 20, 0, 20]
        pickup = {pair[0]: name for name, pair in pairs.items()}
        delivery = {pair[1]: name for name, pair in pairs.items()}

        def evaluate(route):
            current, time, load, opened = 0, 0, 0, set()
            distance = 0
            for node in route:
                travel = abs(position[current] - position[node])
                time += travel
                distance += travel
                if time > latest[node]:
                    return None
                if node in pickup:
                    opened.add(pickup[node])
                    load += 1
                else:
                    if delivery[node] not in opened:
                        return None
                    opened.remove(delivery[node])
                    load -= 1
                if load < 0 or load > 1:
                    return None
                current = node
            if opened:
                return None
            return distance + abs(position[current] - position[0])

        def insert(route, request):
            original = evaluate(route)
            pu, de = pairs[request]
            options = []
            for i in range(len(route) + 1):
                for j in range(i + 1, len(route) + 2):
                    candidate = [*route[:i], pu, *route[i:j - 1], de, *route[j - 1:]]
                    cost = evaluate(candidate)
                    if cost is not None:
                        options.append((cost - original, candidate))
            return min(options) if options else None

        result, remaining = REGRET.regret_k_insert([[], []], ["a", "b", "blocked"], 2, insert)
        self.assertEqual(remaining, ["blocked"])
        self.assertEqual(sorted(node for route in result for node in route), [1, 2, 3, 4])
        self.assertTrue(all(evaluate(route) is not None for route in result))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            REGRET.regret_k_insert([[]], [1], 0, lambda route, req: None)
        with self.assertRaises(ValueError):
            REGRET.regret_k_insert([[]], [1, 1], 2, lambda route, req: None)
        with self.assertRaises(ValueError):
            REGRET.regret_k_insert([[]], [1], 1, lambda route, req: (float("nan"), [req]))


if __name__ == "__main__":
    unittest.main()
