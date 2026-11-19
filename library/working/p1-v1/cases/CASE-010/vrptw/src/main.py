from __future__ import annotations

from pathlib import Path
import argparse
import csv

from src.aco.io import load_solomon_instance
from src.aco.problem import build_problem
from src.aco.solver import ACOConfig, ACOSolver
from src.aco.plotting import plot_solution, plot_convergence

def _scalar_cost(score: tuple[int, float]) -> float:
    return score[0] * 1e9 + score[1]

def save_history_csv(path: Path, history: list[tuple[int, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iter", "best_vehicles", "best_penalized_distance", "best_scalar_cost"])
        for i, (k, d) in enumerate(history):
            w.writerow([i, k, d, _scalar_cost((k, d))])

def save_best_solution_csv(
    path: Path,
    solution: list[list[int]],
    score: tuple[int, float],
    evaluation,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["best_vehicles", score[0]])
        w.writerow(["best_penalized_distance", score[1]])
        w.writerow(["best_scalar_cost", _scalar_cost(score)])
        w.writerow(["total_distance", evaluation.total_distance])
        w.writerow(["time_window_violation", evaluation.time_window_violation])
        w.writerow(["capacity_violation", evaluation.capacity_violation])
        w.writerow([])
        w.writerow(["route_id", "customers"])
        for ridx, route in enumerate(solution):
            w.writerow([ridx, " ".join(str(x) for x in route)])

def save_runs_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=str, default="data/solomon-100/In/c101.txt")
    ap.add_argument("--out_dir", type=str, default="results/demo")
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--m", type=int, default=20)
    ap.add_argument("--T", type=int, default=100)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=5.0)
    ap.add_argument("--rho", type=float, default=0.3)
    ap.add_argument("--p_random", type=float, default=0.01)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    customers, capacity = load_solomon_instance(args.instance)
    problem = build_problem(customers, capacity)

    cfg = ACOConfig(
        m=args.m,
        T=args.T,
        alpha=args.alpha,
        beta=args.beta,
        rho=args.rho,
        p_random=args.p_random,
        tau0=1.0,
        deposit_q=1.0,
        seed=args.seed,
    )

    solver = ACOSolver(problem, cfg)
    res = solver.solve()

    save_best_solution_csv(out_dir / "best_solution.csv", res.best_solution, res.best_score, res.best_evaluation)
    save_history_csv(out_dir / "convergence.csv", res.best_history)

    cost_history = [_scalar_cost(s) for s in res.best_history]
    plot_solution(
        problem,
        res.best_solution,
        out_dir / "best_solution.png",
        title=f"Best: vehicles={res.best_score[0]} dist={res.best_evaluation.total_distance:.3f}",
    )
    plot_convergence(cost_history, out_dir / "convergence.png", title="Convergence")

    print(f"Best vehicles: {res.best_score[0]}")
    print(f"Best distance: {res.best_evaluation.total_distance:.6f}")
    print(f"TW violation: {res.best_evaluation.time_window_violation:.6f}")
    print(f"CAP violation: {res.best_evaluation.capacity_violation:.6f}")
    print(f"Elapsed [s]: {res.elapsed_s:.3f}")

    run_summary = {
        "instance": args.instance,
        "seed": args.seed,
        "m": args.m,
        "T": args.T,
        "alpha": args.alpha,
        "beta": args.beta,
        "rho": args.rho,
        "p_random": args.p_random,
        "best_vehicles": res.best_score[0],
        "best_total_distance": res.best_evaluation.total_distance,
        "best_tw_violation": res.best_evaluation.time_window_violation,
        "best_cap_violation": res.best_evaluation.capacity_violation,
        "best_scalar_cost": _scalar_cost(res.best_score),
        "elapsed_s": res.elapsed_s,
    }
    save_runs_csv(out_dir / "run_summary.csv", [run_summary])

if __name__ == "__main__":
    main()