"""Remove related customers and rebuild with feasible least-cost insertion."""

from random import Random

from greedy_insertion import greedy_insert
from relocate import solution_length
from savings import savings_routes
from shaw_removal import shaw_removal


def solve(distance, demands, capacity, seed=0, rounds=12):
    rng = Random(seed)
    incumbent = savings_routes(distance, demands, capacity)
    value = solution_length(distance, incumbent)
    identity = {v: v for v in range(1, len(distance))}
    remove_count = min(3, len(identity))
    if remove_count == 0:
        return incumbent
    for _ in range(rounds):
        partial, removed = shaw_removal(
            incumbent, identity, remove_count, 4, lambda a, b: distance[a][b], rng
        )
        removed.sort(key=lambda vertex: (-demands[vertex], vertex))
        trial = greedy_insert(distance, demands, capacity, partial, removed)
        length = solution_length(distance, trial)
        if length < value:
            incumbent, value = trial, length
    return incumbent
