"""Exact small-instance assignment to fixed vehicle-route seeds."""

from functools import cache


def seeded_assignment(distance, demands, capacity, seeds):
    """Return seed-based customer groups, or None if this assignment is infeasible."""
    seeds = tuple(seeds)
    n = len(distance)
    if len(set(seeds)) != len(seeds) or any(not 0 < v < n for v in seeds):
        raise ValueError("seeds must be distinct customers")
    if capacity < 0 or any(not 0 <= demands[v] <= capacity for v in range(1, n)):
        raise ValueError("customer cannot be served by a singleton route")
    remaining = [v for v in range(1, n) if v not in seeds]
    weights = [
        [
            min(
                distance[0][v] + distance[v][seed] + distance[seed][0],
                distance[0][seed] + distance[seed][v] + distance[v][0],
            ) - distance[0][seed] - distance[seed][0]
            for seed in seeds
        ]
        for v in remaining
    ]

    @cache
    def search(index, spare):
        if index == len(remaining):
            return 0, ()
        demand = demands[remaining[index]]
        best = None
        for slot, free in enumerate(spare):
            if demand > free:
                continue
            subproblem = search(index + 1, spare[:slot] + (free - demand,) + spare[slot + 1:])
            if subproblem is not None:
                cost, assignment = subproblem
                candidate = cost + weights[index][slot], (slot,) + assignment
                if best is None or candidate < best:
                    best = candidate
        return best

    result = search(0, tuple(capacity - demands[v] for v in seeds))
    if result is None:
        return None
    clusters = [[v] for v in seeds]
    for node, slot in zip(remaining, result[1]):
        clusters[slot].append(node)
    return clusters
