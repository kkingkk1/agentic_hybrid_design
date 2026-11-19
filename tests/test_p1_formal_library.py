"""Verify the frozen P1 first edition and run its new standalone cases."""

import builtins
import hashlib
import itertools
import json
import math
from pathlib import Path
from random import Random
import re
import sys
from types import ModuleType
import unittest

from scripts.p1_library_reader import LibraryReader


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "p1-v1-20261118-01"
INHERITED_CASES = {"CASE-001", "CASE-004", "CASE-006", "CASE-009", "CASE-010"}
NEW_CASES = {f"CASE-{number:03}" for number in range(11, 41)}


def reconstruct_solver(material):
    """Restore the declared Python files in separate module namespaces."""
    parts = re.split(r"^# --- FILE: ([^/\n]+) ---\n", material, flags=re.MULTILINE)
    if parts[0].strip():
        raise ValueError("material precedes the first file marker")
    files = dict(zip(parts[1::2], parts[2::2], strict=True))
    if len(files) != len(parts[1::2]):
        raise ValueError("duplicate case file markers")
    program = files.pop("solver.py")
    modules = {}

    def import_file(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules:
            return modules[name]
        if level == 0 and name.partition(".")[0] in sys.stdlib_module_names:
            return builtins.__import__(name, globals, locals, fromlist, level)
        raise ImportError(f"case requires an undeclared module {name}")

    namespace_builtins = dict(vars(builtins), __import__=import_file)
    for name, source in files.items():
        module = ModuleType(Path(name).stem)
        module.__dict__["__builtins__"] = namespace_builtins
        exec(compile(source, name, "exec"), module.__dict__)
        modules[module.__name__] = module
    namespace = {"__builtins__": namespace_builtins}
    exec(compile(program, "solver.py", "exec"), namespace)
    return namespace["solve"]


def matrix_for(points, continuous):
    if continuous:
        return [[math.hypot(x - a, y - b) for a, b in points] for x, y in points]
    return [[abs(x - a) + abs(y - b) for a, b in points] for x, y in points]


def cycle_length(distance, tour):
    costs = [distance[a][b] for a, b in zip(tour, tour[1:] + tour[:1])]
    return sum(costs) if all(type(value) is int for value in costs) else math.fsum(costs)


def route_cost(distance, routes):
    return sum(cycle_length(distance, [0, *route]) for route in routes)


def brute_cvrp_cost(distance, demands, capacity):
    """Enumerate complete orders and every split independently of the case."""
    customers = range(1, len(distance))
    best = math.inf
    for order in itertools.permutations(customers):
        for cuts in range(1 << (len(customers) - 1)):
            groups = [[]]
            for index, customer in enumerate(order):
                groups[-1].append(customer)
                if index < len(order) - 1 and cuts & (1 << index):
                    groups.append([])
            if all(sum(demands[v] for v in group) <= capacity for group in groups):
                best = min(best, route_cost(distance, groups))
    return best


class FormalLibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT / "library" / "versions" / SNAPSHOT
        manifest_dir = ROOT / "library" / "manifests" / SNAPSHOT
        manifests = list(manifest_dir.glob("manifest-*.json"))
        if len(manifests) != 1:
            raise AssertionError(f"expected one manifest for {SNAPSHOT}, got {len(manifests)}")
        cls.manifest = manifests[0]
        cls.reader = LibraryReader(cls.root, manifest=cls.manifest)

    def test_catalog_and_file_hashes(self):
        catalog = self.reader.catalog()
        algorithms = {record["algorithm_id"] for record in catalog["algorithms"]}
        cases = {record["case_id"] for record in catalog["cases"]}
        self.assertEqual(algorithms, {f"ALG-{number:03}" for number in range(1, 66)})
        self.assertEqual(cases, INHERITED_CASES | NEW_CASES)
        self.assertEqual(len(self.reader.load(sorted(algorithms | cases))), 100)

        manifest = json.loads(self.manifest.read_bytes())
        self.assertEqual(manifest["snapshot_id"], SNAPSHOT)
        expected = manifest["files"]
        paths = {p.relative_to(self.root).as_posix(): p for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(paths.keys(), expected.keys())
        self.assertEqual(len(paths), 399)
        for name, path in paths.items():
            content = path.read_bytes()
            self.assertEqual(len(content), expected[name]["size"], name)
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected[name]["sha256"], name)

    def test_reconstructed_new_cases(self):
        rng = Random(651735)
        records = self.reader.load(sorted(NEW_CASES))
        for record in records:
            case = record["entry"]
            number = int(case["case_id"].split("-")[-1])
            solve = reconstruct_solver(case["code"])
            is_tsp = number <= 23 or number == 39
            mid_size = 8 if is_tsp else 7
            fixtures = [(1, False), (3, False), (6, False), (mid_size, False), (mid_size, True), (9, False)]
            for size, continuous in fixtures:
                with self.subTest(case=case["case_id"], size=size, continuous=continuous):
                    if is_tsp:
                        self.check_tsp(solve, number, size, continuous, rng)
                    else:
                        self.check_cvrp(solve, number, size, continuous, rng)

    def check_tsp(self, solve, number, size, continuous, rng):
        points = [(rng.randrange(1, 30), rng.randrange(1, 30)) for _ in range(size)]
        if number in (15, 39):
            distance = [[rng.randrange(1, 31) if i != j else 0 for j in range(size)] for i in range(size)]
        else:
            distance = matrix_for(points, continuous and number != 23)
        original = tuple(map(tuple, distance))
        tour = solve(distance)
        self.assertEqual(sorted(tour), list(range(size)))
        self.assertEqual(tuple(map(tuple, distance)), original)
        cost = cycle_length(distance, tour)
        self.assertTrue(math.isfinite(cost))
        if number in (23, 39):
            exact = min(
                cycle_length(distance, [0, *permutation])
                for permutation in itertools.permutations(range(1, size))
            )
            self.assertEqual(cost, exact)

    def check_cvrp(self, solve, number, size, continuous, rng):
        points = [(0, 0), *[(rng.randrange(-10, 10), rng.randrange(-10, 10)) for _ in range(size - 1)]]
        distance = matrix_for(points, continuous and number not in (37, 40))
        demands = [0] + [rng.randrange(4) for _ in range(size - 1)]
        capacity = 4
        if number in (25, 38):
            arguments = (points,)
        elif number == 26:
            arguments = ([1, 2] if size > 2 else [],)
        else:
            arguments = ()
        original = tuple(map(tuple, distance)), tuple(demands)
        routes = solve(distance, demands, capacity, *arguments)
        self.assertEqual(sorted(itertools.chain.from_iterable(routes)), list(range(1, size)))
        self.assertTrue(all(route and sum(demands[v] for v in route) <= capacity for route in routes))
        self.assertEqual((tuple(map(tuple, distance)), tuple(demands)), original)
        cost = route_cost(distance, routes)
        self.assertTrue(math.isfinite(cost))
        if number == 37 and 2 < size <= 7:
            self.assertEqual(cost, brute_cvrp_cost(distance, demands, capacity))
        if number == 40:
            self.assertLessEqual(cost, route_cost(distance, [[v] for v in range(1, size)]))


if __name__ == "__main__":
    unittest.main()
