"""Generate feasible routes by perturbation and exact recombination of a route pool."""

from random import Random

from greedy_insertion import greedy_insert
from random_removal import uniform_remove
from relocate import best_relocate, solution_length
from route_partition import partition_routes
from savings import savings_routes


def solve(distance, demands, capacity, seed=0, rounds=8):
    if len(distance) > 13:
        raise ValueError("reference route-pool partitioning is limited to 12 customers")
    rng = Random(seed)
    customers = range(1, len(distance))
    incumbent = savings_routes(distance, demands, capacity)
    length = solution_length(distance, incumbent)
    pool = {tuple(route) for route in incumbent}
    remove_count = min(3, len(customers))
    for _ in range(rounds):
        partial, removed = uniform_remove(incumbent, remove_count, rng)
        trial = greedy_insert(distance, demands, capacity, partial, removed)
        trial = best_relocate(distance, demands, capacity, trial)
        pool.update(tuple(route) for route in trial)
        value = solution_length(distance, trial)
        if value < length:
            incumbent, length = trial, value
    combined = partition_routes(distance, customers, sorted(pool))
    if combined is not None and solution_length(distance, combined) < length:
        return combined
    return incumbent
