from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import argparse
import csv
import time
import statistics
import matplotlib.pyplot as plt

from ..aco.io import load_solomon_instance
from ..aco.problem import build_problem, VRPTWProblem, VRPTWEvaluation
from ..aco.solver import ACOConfig, ACOSolver, ACOResult
from ..aco.plotting import plot_solution, plot_convergence_band

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def cfg_to_tag(cfg: ACOConfig) -> str:
    return (
        f"m{cfg.m}_T{cfg.T}_a{cfg.alpha}_b{cfg.beta}"
        f"_rho{cfg.rho}_pr{cfg.p_random}"
    )

def scalar_cost(score: Tuple[int, float]) -> float:
    return score[0] * 1e9 + score[1]

def save_runs_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def save_history_csv(path: Path, histories: List[List[Tuple[int, float]]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iter", "run_id", "best_vehicles", "best_penalized_distance", "best_scalar_cost"])
        for run_id, hist in enumerate(histories):
            for it, (k, d) in enumerate(hist):
                w.writerow([it, run_id, k, d, scalar_cost((k, d))])

def save_population_history_csv(path: Path, results: List[ACOResult]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iter", "run_id", "iter_best", "iter_mean", "iter_worst"])
        for run_id, res in enumerate(results):
            T = len(res.iter_best)
            for it in range(T):
                w.writerow([it, run_id, res.iter_best[it], res.iter_mean[it], res.iter_worst[it]])

def save_best_solution_csv(
    path: Path,
    solution: List[List[int]],
    score: Tuple[int, float],
    evaluation: VRPTWEvaluation,
) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["best_vehicles", score[0]])
        w.writerow(["best_penalized_distance", score[1]])
        w.writerow(["best_scalar_cost", scalar_cost(score)])
        w.writerow(["total_distance", evaluation.total_distance])
        w.writerow(["time_window_violation", evaluation.time_window_violation])
        w.writerow(["capacity_violation", evaluation.capacity_violation])
        w.writerow([])
        w.writerow(["route_id", "customers"])
        for ridx, route in enumerate(solution):
            w.writerow([ridx, " ".join(str(x) for x in route)])

def save_selected_runs_csv(path: Path, selected: Dict[str, int], results: List[ACOResult]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "label",
                "run_id",
                "best_vehicles",
                "best_penalized_distance",
                "best_scalar_cost",
                "total_distance",
                "time_window_violation",
                "capacity_violation",
            ]
        )
        for label, idx in selected.items():
            res = results[idx]
            w.writerow(
                [
                    label,
                    idx,
                    res.best_score[0],
                    res.best_score[1],
                    scalar_cost(res.best_score),
                    res.best_evaluation.total_distance,
                    res.best_evaluation.time_window_violation,
                    res.best_evaluation.capacity_violation,
                ]
            )

def compute_stats(values: List[float], prefix: str) -> Dict[str, float]:
    mean = statistics.fmean(values)
    median = statistics.median(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        f"{prefix}_min": float(min(values)),
        f"{prefix}_mean": float(mean),
        f"{prefix}_median": float(median),
        f"{prefix}_std": float(std),
        f"{prefix}_max": float(max(values)),
    }

def run_one(problem: VRPTWProblem, cfg: ACOConfig) -> ACOResult:
    solver = ACOSolver(problem, cfg)
    return solver.solve()

def plot_param_comparisons(summary_rows: List[Dict], out_dir: Path, y_key: str) -> None:
    params = ["m", "T", "alpha", "beta", "rho", "p_random"]

    for p in params:
        xs = sorted(set(row[p] for row in summary_rows))
        if len(xs) <= 1:
            continue

        x_to_vals: Dict[float, List[float]] = {x: [] for x in xs}
        for row in summary_rows:
            x_to_vals[row[p]].append(row[y_key])

        x_plot: List[float] = []
        y_plot: List[float] = []
        for x in xs:
            x_plot.append(x)
            y_plot.append(statistics.fmean(x_to_vals[x]))

        plt.figure()
        plt.plot(x_plot, y_plot, marker="o")
        plt.xlabel(p)
        plt.ylabel(y_key)
        plt.title(f"Porownanie parametru {p} wzgledem {y_key}")
        plt.tight_layout()
        plt.savefig(out_dir / f"compare_{p}.png")
        plt.close()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", type=str, nargs="+", default=["c204.txt", "r102.txt", "rc106.txt"])
    ap.add_argument("--in_dir", type=str, default="data/solomon-100/In")
    ap.add_argument("--out_dir", type=str, default="results/experiments")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--base_seed", type=int, default=123)

    ap.add_argument("--m_list", type=int, nargs="+", default=[10, 20, 50])
    ap.add_argument("--T_list", type=int, nargs="+", default=[50, 100])
    ap.add_argument("--alpha_list", type=float, nargs="+", default=[1.0])
    ap.add_argument("--beta_list", type=float, nargs="+", default=[5.0])
    ap.add_argument("--rho_list", type=float, nargs="+", default=[0.3])
    ap.add_argument("--p_random_list", type=float, nargs="+", default=[0.01])

    args = ap.parse_args()

    base_out = Path(args.out_dir)
    ensure_dir(base_out)

    configs: List[ACOConfig] = []
    for m in args.m_list:
        for T in args.T_list:
            for alpha in args.alpha_list:
                for beta in args.beta_list:
                    for rho in args.rho_list:
                        for pr in args.p_random_list:
                            configs.append(
                                ACOConfig(
                                    m=m,
                                    T=T,
                                    alpha=alpha,
                                    beta=beta,
                                    rho=rho,
                                    p_random=pr,
                                    tau0=1.0,
                                    deposit_q=1.0,
                                    seed=None,
                                )
                            )

    print(f"Configurations: {len(configs)} | repeats: {args.repeats} | instances: {len(args.instances)}")

    for inst_name in args.instances:
        inst_path = Path(args.in_dir) / inst_name
        customers, capacity = load_solomon_instance(inst_path)
        problem = build_problem(customers, capacity)

        inst_out = base_out / inst_name.replace(".txt", "")
        ensure_dir(inst_out)

        summary_rows: List[Dict] = []

        for cfg in configs:
            tag = cfg_to_tag(cfg)
            cfg_dir = inst_out / tag
            ensure_dir(cfg_dir)

            run_rows: List[Dict] = []
            histories: List[List[Tuple[int, float]]] = []
            results: List[ACOResult] = []

            best_overall_cost = float("inf")
            best_overall_solution: List[List[int]] = []
            best_overall_score: Tuple[int, float] = (10**9, float("inf"))
            best_overall_eval = problem.evaluate([])

            for r in range(args.repeats):
                run_seed = args.base_seed + r
                run_cfg = ACOConfig(
                    m=cfg.m,
                    T=cfg.T,
                    alpha=cfg.alpha,
                    beta=cfg.beta,
                    rho=cfg.rho,
                    p_random=cfg.p_random,
                    tau0=1.0,
                    deposit_q=1.0,
                    seed=run_seed,
                )

                t0 = time.perf_counter()
                res = run_one(problem, run_cfg)
                elapsed = time.perf_counter() - t0

                results.append(res)
                histories.append(res.best_history)

                run_cost = scalar_cost(res.best_score)
                if run_cost < best_overall_cost:
                    best_overall_cost = run_cost
                    best_overall_solution = [list(rt) for rt in res.best_solution]
                    best_overall_score = res.best_score
                    best_overall_eval = res.best_evaluation

                run_rows.append(
                    {
                        "run_id": r,
                        "seed": run_seed,
                        "best_vehicles": res.best_score[0],
                        "best_penalized_distance": res.best_score[1],
                        "best_scalar_cost": run_cost,
                        "best_total_distance": res.best_evaluation.total_distance,
                        "best_tw_violation": res.best_evaluation.time_window_violation,
                        "best_cap_violation": res.best_evaluation.capacity_violation,
                        "elapsed_s": elapsed,
                        "m": run_cfg.m,
                        "T": run_cfg.T,
                        "alpha": run_cfg.alpha,
                        "beta": run_cfg.beta,
                        "rho": run_cfg.rho,
                        "p_random": run_cfg.p_random,
                    }
                )

                print(
                    f"{inst_name} | {tag} | run {r+1}/{args.repeats}: "
                    f"veh={res.best_score[0]} dist={res.best_evaluation.total_distance:.3f} "
                    f"cost={run_cost:.3f} time={elapsed:.3f}s"
                )

            save_runs_csv(cfg_dir / "runs.csv", run_rows)
            save_history_csv(cfg_dir / "history.csv", histories)
            save_population_history_csv(cfg_dir / "population_history.csv", results)
            save_best_solution_csv(
                cfg_dir / "best_solution_overall.csv",
                best_overall_solution,
                best_overall_score,
                best_overall_eval,
            )

            histories_cost = [[scalar_cost(s) for s in h] for h in histories]
            plot_convergence_band(
                histories=histories_cost,
                out_path=cfg_dir / "convergence_mean_minmax.png",
                title=f"Srednia z {args.repeats} uruchomien (min-max) | {tag}",
                band="minmax",
            )

            run_costs = [scalar_cost(res.best_score) for res in results]
            best_idx = min(range(len(run_costs)), key=lambda i: run_costs[i])
            worst_idx = max(range(len(run_costs)), key=lambda i: run_costs[i])
            sorted_idx = sorted(range(len(run_costs)), key=lambda i: run_costs[i])
            median_idx = sorted_idx[len(sorted_idx) // 2]
            selected = {"best": best_idx, "median": median_idx, "worst": worst_idx}

            save_selected_runs_csv(cfg_dir / "selected_runs.csv", selected, results)

            plot_solution(
                problem=problem,
                solution=best_overall_solution,
                out_path=cfg_dir / "solution_best_overall.png",
                title=f"BestOverall veh={best_overall_score[0]} dist={best_overall_eval.total_distance:.3f} | {tag}",
            )

            for label, idx in selected.items():
                sol = [list(rt) for rt in results[idx].best_solution]
                ev = results[idx].best_evaluation
                sc = results[idx].best_score
                plot_solution(
                    problem=problem,
                    solution=sol,
                    out_path=cfg_dir / f"solution_{label}.png",
                    title=f"{label} veh={sc[0]} dist={ev.total_distance:.3f} | {tag}",
                )

            best_costs = [float(row["best_scalar_cost"]) for row in run_rows]
            stats_cost = compute_stats(best_costs, "cost")

            best_total_dist = [float(row["best_total_distance"]) for row in run_rows]
            stats_dist = compute_stats(best_total_dist, "total_distance")

            best_veh = [float(row["best_vehicles"]) for row in run_rows]
            stats_veh = compute_stats(best_veh, "vehicles")

            summary_row = {
                "config_dir": str(cfg_dir),
                "tag": tag,
                "instance": str(inst_path),
                "n_runs": args.repeats,
                "m": cfg.m,
                "T": cfg.T,
                "alpha": cfg.alpha,
                "beta": cfg.beta,
                "rho": cfg.rho,
                "p_random": cfg.p_random,
                **stats_cost,
                **stats_dist,
                **stats_veh,
                "mean_elapsed_s": float(statistics.fmean([row["elapsed_s"] for row in run_rows])),
                "best_overall_vehicles": best_overall_score[0],
                "best_overall_total_distance": float(best_overall_eval.total_distance),
                "best_overall_tw_violation": float(best_overall_eval.time_window_violation),
                "best_overall_cap_violation": float(best_overall_eval.capacity_violation),
                "best_overall_scalar_cost": float(best_overall_cost),
            }
            summary_rows.append(summary_row)

        save_runs_csv(inst_out / "summary.csv", summary_rows)
        plot_param_comparisons(summary_rows, inst_out, y_key="cost_mean")

    print("DONE")

if __name__ == "__main__":
    main()