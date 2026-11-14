from __future__ import annotations

from pathlib import Path
from typing import List, Sequence
import matplotlib.pyplot as plt

from .problem import VRPTWProblem

def plot_solution(problem: VRPTWProblem, solution: Sequence[Sequence[int]], out_path: str | Path, title: str = "") -> None:
    plt.figure()

    depot = problem.depot
    plt.scatter([depot.x], [depot.y], marker="s")
    plt.text(depot.x, depot.y, "0")

    for route in solution:
        if not route:
            continue
        xs = [depot.x]
        ys = [depot.y]
        for i in route:
            c = problem.customers[i]
            xs.append(c.x)
            ys.append(c.y)
        xs.append(depot.x)
        ys.append(depot.y)
        plt.plot(xs, ys, marker="o")
        for i in route:
            c = problem.customers[i]
            plt.text(c.x, c.y, str(c.idx))

    if title:
        plt.title(title)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

def plot_convergence(best_history: List[float], out_path: str | Path, title: str = "") -> None:
    plt.figure()
    plt.plot(best_history)
    if title:
        plt.title(title)
    plt.xlabel("iteracja")
    plt.ylabel("najlepszy koszt")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

def plot_convergence_band(
    histories: List[List[float]],
    out_path: str | Path,
    title: str = "",
    band: str = "minmax",
) -> None:
    import math

    T = len(histories[0])
    for h in histories:
        if len(h) != T:
            raise ValueError("Różne długości historii")

    mean = []
    lo = []
    hi = []

    for t in range(T):
        vals = [h[t] for h in histories]
        m = sum(vals) / len(vals)
        mean.append(m)

        if band == "minmax":
            lo.append(min(vals))
            hi.append(max(vals))
        elif band == "std":
            var = sum((x - m) ** 2 for x in vals) / len(vals)
            s = math.sqrt(var)
            lo.append(m - s)
            hi.append(m + s)
        else:
            raise ValueError("band must be 'minmax' or 'std'")

    plt.figure()
    plt.plot(mean)
    plt.fill_between(range(T), lo, hi, alpha=0.2)
    if title:
        plt.title(title)
    plt.xlabel("iteracja")
    plt.ylabel("koszt")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()