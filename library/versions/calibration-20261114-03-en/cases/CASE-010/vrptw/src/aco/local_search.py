from __future__ import annotations

from typing import List, Sequence, Tuple, Optional

from .problem import VRPTWProblem

def _is_feasible(problem: VRPTWProblem, route: Sequence[int]) -> bool:
    m = problem.route_metrics(route)
    return m.time_window_violation <= 0.0 and m.capacity_violation <= 0.0

def two_opt_improve_route(
    problem: VRPTWProblem,
    route: List[int],
    *,
    max_passes: int = 3,
    max_moves: int = 200,
) -> List[int]:
    if len(route) < 4:
        return list(route)

    best = list(route)
    if not _is_feasible(problem, best):
        return list(route)

    best_dist = problem.route_metrics(best).distance
    moves = 0

    for _ in range(max_passes):
        improved = False
        n = len(best)

        for i in range(n - 1):
            for j in range(i + 2, n + 1):
                if moves >= max_moves:
                    return best

                cand = best[:i] + list(reversed(best[i:j])) + best[j:]
                moves += 1

                if not _is_feasible(problem, cand):
                    continue

                cand_dist = problem.route_metrics(cand).distance
                if cand_dist + 1e-12 < best_dist:
                    best = cand
                    best_dist = cand_dist
                    improved = True
                    break

            if improved:
                break

        if not improved:
            break

    return best

def two_opt_improve_solution(
    problem: VRPTWProblem,
    solution: Sequence[Sequence[int]],
    *,
    max_passes: int = 3,
    max_moves_per_route: int = 200,
) -> List[List[int]]:
    improved: List[List[int]] = []
    for r in solution:
        rr = list(r)
        improved.append(two_opt_improve_route(problem, rr, max_passes=max_passes, max_moves=max_moves_per_route))
    return improved

def _best_insertion_for_customer(
    problem: VRPTWProblem,
    route: Sequence[int],
    customer: int,
) -> Optional[Tuple[List[int], float]]:
    best_route: Optional[List[int]] = None
    best_dist: float = 0.0

    base = list(route)
    for pos in range(len(base) + 1):
        cand = base[:pos] + [customer] + base[pos:]
        if not _is_feasible(problem, cand):
            continue
        d = problem.route_metrics(cand).distance
        if best_route is None or d < best_dist:
            best_route = cand
            best_dist = d

    if best_route is None:
        return None
    return best_route, best_dist

def relocate_eliminate_one_route(
    problem: VRPTWProblem,
    solution: Sequence[Sequence[int]],
) -> Optional[List[List[int]]]:
    routes: List[List[int]] = [list(r) for r in solution if len(r) > 0]
    if len(routes) <= 1:
        return None

    idx_order = sorted(range(len(routes)), key=lambda i: len(routes[i]))
    for src_idx in idx_order:
        src_route = routes[src_idx]
        if not src_route:
            continue

        working: List[List[int]] = [list(r) for r in routes]
        removed = working.pop(src_idx)

        ok_all = True
        for cust in removed:
            best_target_idx: Optional[int] = None
            best_target_route: Optional[List[int]] = None
            best_target_dist: float = 0.0

            for t_idx in range(len(working)):
                ins = _best_insertion_for_customer(problem, working[t_idx], cust)
                if ins is None:
                    continue
                cand_route, cand_dist = ins
                if best_target_route is None or cand_dist < best_target_dist:
                    best_target_idx = t_idx
                    best_target_route = cand_route
                    best_target_dist = cand_dist

            if best_target_route is None or best_target_idx is None:
                ok_all = False
                break

            working[best_target_idx] = best_target_route

        if ok_all:
            return working

    return None