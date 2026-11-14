from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import time
import random

from .problem import VRPTWProblem, VRPTWEvaluation
from .ant import construct_solution, AntResult
from .local_search import two_opt_improve_solution, relocate_eliminate_one_route

@dataclass
class ACOConfig:
    m: int
    T: int
    alpha: float
    beta: float
    rho: float
    p_random: float
    tau0: float = 1.0
    deposit_q: float = 1.0
    seed: Optional[int] = None
    ls_enabled: bool = True
    ls_max_passes: int = 3
    ls_max_moves_per_route: int = 200

@dataclass
class ACOResult:
    best_solution: List[List[int]]
    best_score: Tuple[int, float]
    best_evaluation: VRPTWEvaluation
    best_history: List[Tuple[int, float]]
    elapsed_s: float
    iter_best: List[float]
    iter_mean: List[float]
    iter_worst: List[float]

def better_score(a: Tuple[int, float], b: Tuple[int, float]) -> bool:
    if a[0] != b[0]:
        return a[0] < b[0]
    return a[1] < b[1]

class ACOSolver:
    def __init__(self, problem: VRPTWProblem, cfg: ACOConfig):
        self.problem = problem
        self.cfg = cfg
        n = problem.n
        self.pher = [[cfg.tau0] * n for _ in range(n)]
        self.best_solution: List[List[int]] = []
        self.best_score: Tuple[int, float] = (10**9, float("inf"))
        self.best_evaluation: VRPTWEvaluation = problem.evaluate([])
        self.best_history: List[Tuple[int, float]] = []
        self.rng = random.Random(cfg.seed)

    @staticmethod
    def _scalar_cost(score: Tuple[int, float]) -> float:
        return score[0] * 1e9 + score[1]

    def _deposit_edges(self, solution: List[List[int]], delta: float) -> None:
        for route in solution:
            if not route:
                continue
            a = 0
            b = route[0]
            self.pher[a][b] += delta
            self.pher[b][a] += delta
            for i in range(len(route) - 1):
                a = route[i]
                b = route[i + 1]
                self.pher[a][b] += delta
                self.pher[b][a] += delta
            a = route[-1]
            b = 0
            self.pher[a][b] += delta
            self.pher[b][a] += delta

    def _improve_iter_best(self, ar: AntResult) -> AntResult:
        cfg = self.cfg
        if not cfg.ls_enabled:
            return ar

        improved_solution = ar.solution

        relocated = relocate_eliminate_one_route(self.problem, improved_solution)
        if relocated is not None:
            improved_solution = relocated

        improved_solution = two_opt_improve_solution(
            self.problem,
            improved_solution,
            max_passes=cfg.ls_max_passes,
            max_moves_per_route=cfg.ls_max_moves_per_route,
        )

        ev = self.problem.evaluate(improved_solution)
        if ev.time_window_violation > 0.0 or ev.capacity_violation > 0.0:
            return ar

        sc = self.problem.score(improved_solution)
        if better_score(sc, ar.score):
            return AntResult(solution=improved_solution, score=sc, evaluation=ev)
        return ar

    def step(self) -> Tuple[List[AntResult], AntResult]:
        cfg = self.cfg
        ants: List[AntResult] = []
        iter_best: Optional[AntResult] = None

        for _ in range(cfg.m):
            ar = construct_solution(
                problem=self.problem,
                pher=self.pher,
                alpha=cfg.alpha,
                beta=cfg.beta,
                p_random=cfg.p_random,
                rng=self.rng,
            )
            ants.append(ar)
            if iter_best is None or better_score(ar.score, iter_best.score):
                iter_best = ar

        assert iter_best is not None
        iter_best = self._improve_iter_best(iter_best)

        evap = 1.0 - cfg.rho
        n = self.problem.n
        for i in range(n):
            row = self.pher[i]
            for j in range(n):
                row[j] *= evap

        for ant in ants:
            denom = max(1e-12, self._scalar_cost(ant.score))
            delta = cfg.deposit_q / denom
            self._deposit_edges(ant.solution, delta)

        denom_best = max(1e-12, self._scalar_cost(iter_best.score))
        delta_best = cfg.deposit_q / denom_best
        self._deposit_edges(iter_best.solution, delta_best)

        if better_score(iter_best.score, self.best_score):
            self.best_score = iter_best.score
            self.best_solution = [list(r) for r in iter_best.solution]
            self.best_evaluation = iter_best.evaluation

        self.best_history.append(self.best_score)
        return ants, iter_best

    def solve(self) -> ACOResult:
        t0 = time.perf_counter()

        iter_best: List[float] = []
        iter_mean: List[float] = []
        iter_worst: List[float] = []

        for _ in range(self.cfg.T):
            ants, _ = self.step()
            costs = [self._scalar_cost(a.score) for a in ants]
            iter_best.append(min(costs))
            iter_mean.append(sum(costs) / len(costs))
            iter_worst.append(max(costs))

        elapsed = time.perf_counter() - t0

        return ACOResult(
            best_solution=self.best_solution,
            best_score=self.best_score,
            best_evaluation=self.best_evaluation,
            best_history=self.best_history,
            elapsed_s=elapsed,
            iter_best=iter_best,
            iter_mean=iter_mean,
            iter_worst=iter_worst,
        )