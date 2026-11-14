from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple
import math

@dataclass(frozen=True)
class Customer:
    idx: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_time: float
    service_time: float

@dataclass(frozen=True)
class RouteMetrics:
    distance: float
    end_time: float
    load: float
    time_window_violation: float
    capacity_violation: float

    @property
    def feasible(self) -> bool:
        return self.time_window_violation <= 0.0 and self.capacity_violation <= 0.0

@dataclass(frozen=True)
class VRPTWEvaluation:
    n_vehicles: int
    total_distance: float
    time_window_violation: float
    capacity_violation: float

    @property
    def feasible(self) -> bool:
        return self.time_window_violation <= 0.0 and self.capacity_violation <= 0.0

@dataclass(frozen=True)
class VRPTWProblem:
    customers: List[Customer]
    capacity: float
    dist: List[List[float]]

    @property
    def n(self) -> int:
        return len(self.customers)

    @property
    def depot(self) -> Customer:
        return self.customers[0]

    def route_metrics(self, route: Sequence[int]) -> RouteMetrics:
        time = 0.0
        load = 0.0
        dist_sum = 0.0
        tw_violation = 0.0

        prev = 0

        for node in route:
            c = self.customers[node]

            dist_sum += self.dist[prev][node]
            arrival = time + self.dist[prev][node]

            start_service = max(arrival, c.ready_time)
            if start_service > c.due_time:
                tw_violation += start_service - c.due_time

            time = start_service + c.service_time
            load += c.demand

            prev = node

        if len(route) > 0:
            depot = self.depot
            travel_back = self.dist[prev][0]
            dist_sum += travel_back

            arrival_depot = time + travel_back
            start_depot = max(arrival_depot, depot.ready_time)
            if start_depot > depot.due_time:
                tw_violation += start_depot - depot.due_time

            time = start_depot + depot.service_time

        cap_violation = max(0.0, load - self.capacity)

        return RouteMetrics(
            distance=dist_sum,
            end_time=time,
            load=load,
            time_window_violation=tw_violation,
            capacity_violation=cap_violation,
        )

    def evaluate(self, solution: Sequence[Sequence[int]]) -> VRPTWEvaluation:
        total_dist = 0.0
        tw_v = 0.0
        cap_v = 0.0

        non_empty_routes = [r for r in solution if len(r) > 0]

        for r in non_empty_routes:
            m = self.route_metrics(r)
            total_dist += m.distance
            tw_v += m.time_window_violation
            cap_v += m.capacity_violation

        return VRPTWEvaluation(
            n_vehicles=len(non_empty_routes),
            total_distance=total_dist,
            time_window_violation=tw_v,
            capacity_violation=cap_v,
        )

    def score(
        self,
        solution: Sequence[Sequence[int]],
        *,
        tw_penalty: float = 1e6,
        cap_penalty: float = 1e6,
        lexicographic: bool = True,
    ) -> Tuple[int, float]:
        ev = self.evaluate(solution)
        penalized_dist = (
            ev.total_distance
            + tw_penalty * ev.time_window_violation
            + cap_penalty * ev.capacity_violation
        )

        if lexicographic:
            return ev.n_vehicles, penalized_dist

        big_m = 1e9
        cost = ev.n_vehicles * big_m + penalized_dist
        return 0, cost

    def validate_solution_cover(
        self,
        solution: Sequence[Sequence[int]],
        *,
        require_all_customers: bool = True,
    ) -> Tuple[bool, str]:
        seen: List[int] = []
        for r in solution:
            for v in r:
                seen.append(v)

        if any(v == 0 for v in seen):
            return False, "route contains depot index 0; routes should not include depot explicitly"

        if len(set(seen)) != len(seen):
            return False, "duplicate customer in solution"

        if require_all_customers:
            expected = set(range(1, self.n))
            got = set(seen)
            if got != expected:
                missing = expected - got
                extra = got - expected
                return False, f"solution does not cover all customers; missing={sorted(missing)}, extra={sorted(extra)}"

        return True, "ok"

def build_problem(customers: List[Customer], capacity: float) -> VRPTWProblem:
    if not customers:
        raise ValueError("customers list is empty")

    if customers[0].idx != 0:
        raise ValueError("customers[0] must be depot with idx=0")

    n = len(customers)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = customers[i].x, customers[i].y
        for j in range(i + 1, n):
            xj, yj = customers[j].x, customers[j].y
            d = math.hypot(xi - xj, yi - yj)
            dist[i][j] = d
            dist[j][i] = d

    return VRPTWProblem(customers=customers, capacity=capacity, dist=dist)