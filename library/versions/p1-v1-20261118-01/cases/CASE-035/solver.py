"""Exchange overlapping route blocks between two parents and repair coverage."""

from capacity_split import capacity_split
from greedy_insertion import greedy_insert
from nearest_tour import nearest_tour
from relocate import best_relocate
from savings import savings_routes


def solve(distance, demands, capacity):
    first = savings_routes(distance, demands, capacity)
    second = capacity_split(nearest_tour(distance)[1:][::-1], demands, capacity)
    if not first:
        return first
    width = min(2, len(first), len(second))

    def groups(routes):
        return [
            {(start + offset) % len(routes) for offset in range(width)}
            for start in range(len(routes))
        ]

    first_groups = groups(first)
    second_groups = groups(second)

    def members(routes, group):
        return {v for index in group for v in routes[index]}

    removed, added = max(
        ((a, b) for a in first_groups for b in second_groups),
        key=lambda pair: len(members(first, pair[0]) & members(second, pair[1])),
    )
    inherited = members(second, added)
    trial = [
        [v for v in route if v not in inherited]
        for index, route in enumerate(first)
        if index not in removed
    ]
    trial.extend(second[index][:] for index in sorted(added))
    served = {v for route in trial for v in route}
    missing = sorted(set(range(1, len(distance))) - served, key=lambda v: (-demands[v], v))
    repaired = greedy_insert(distance, demands, capacity, trial, missing)
    return best_relocate(distance, demands, capacity, repaired)
