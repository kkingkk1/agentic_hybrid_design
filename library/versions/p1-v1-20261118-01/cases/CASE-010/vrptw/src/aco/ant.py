from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple
import random

from .problem import VRPTWProblem, VRPTWEvaluation

@dataclass
class AntResult:
    solution: List[List[int]]
    score: Tuple[int, float]
    evaluation: VRPTWEvaluation

def _roulette_choice(items: Sequence[int], weights: Sequence[float], rng: random.Random) -> int:
    total = 0.0
    for w in weights:
        total += w
    if total <= 0.0:
        return rng.choice(list(items))
    r = rng.random() * total
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item
    return items[-1]

def _try_append(
    problem: VRPTWProblem,
    current: int,
    current_time: float,
    current_load: float,
    customer: int,
) -> Tuple[bool, float, float]:
    c = problem.customers[customer]
    travel = problem.dist[current][customer]
    arrival = current_time + travel
    start_service = arrival if arrival >= c.ready_time else c.ready_time
    if start_service > c.due_time:
        return False, current_time, current_load

    new_time = start_service + c.service_time
    new_load = current_load + c.demand
    if new_load > problem.capacity:
        return False, current_time, current_load

    depot = problem.depot
    back_time = new_time + problem.dist[customer][0]
    start_depot = back_time if back_time >= depot.ready_time else depot.ready_time
    if start_depot > depot.due_time:
        return False, current_time, current_load

    return True, new_time, new_load

def construct_solution(
    problem: VRPTWProblem,
    pher: List[List[float]],
    alpha: float,
    beta: float,
    p_random: float,
    rng: random.Random | None = None,
) -> AntResult:
    rng = rng or random

    unserved = set(range(1, problem.n))
    solution: List[List[int]] = []

    while unserved:
        route: List[int] = []
        current = 0
        current_time = 0.0
        current_load = 0.0

        while True:
            candidates: List[int] = []
            for j in sorted(unserved):
                ok, _, _ = _try_append(problem, current, current_time, current_load, j)
                if ok:
                    candidates.append(j)

            if not candidates:
                if not route:
                    raise RuntimeError("No feasible customer from depot; instance may be infeasible under hard constraints")
                break

            candidates.sort()

            if p_random > 0.0 and rng.random() < p_random:
                nxt = rng.choice(candidates)
            else:
                weights: List[float] = []
                for j in candidates:
                    d = problem.dist[current][j]
                    inv_d = 1.0 / d if d > 0.0 else 1e9
                    w = (pher[current][j] ** alpha) * (inv_d ** beta)
                    weights.append(w)
                nxt = _roulette_choice(candidates, weights, rng)

            ok, new_time, new_load = _try_append(problem, current, current_time, current_load, nxt)
            if not ok:
                if not route:
                    raise RuntimeError("Construction stuck at depot; instance may be infeasible under hard constraints")
                break

            route.append(nxt)
            unserved.remove(nxt)
            current = nxt
            current_time = new_time
            current_load = new_load

        solution.append(route)

    ok, msg = problem.validate_solution_cover(solution, require_all_customers=True)
    if not ok:
        raise RuntimeError(f"Invalid solution cover: {msg}")

    evaluation = problem.evaluate(solution)
    score = problem.score(solution)
    return AntResult(solution=solution, score=score, evaluation=evaluation)