"""Branch on a proper assignment cycle and prune by assignment lower bounds."""

from cycle_patching import assignment_cycles
from hungarian import hungarian
from nearest_tour import nearest_tour, tour_length


def solve(distance):
    size = len(distance)
    if size > 9 or any(type(value) is not int or value < 0 for row in distance for value in row):
        raise ValueError("expected at most 9 vertices with nonnegative integer costs")
    best = nearest_tour(distance)
    if size < 3:
        return best
    best_value = tour_length(distance, best)
    limit = (size + 1) * max(1, max(max(row) for row in distance))
    stack = [frozenset()]
    seen = set()
    while stack:
        forbidden = stack.pop()
        if forbidden in seen:
            continue
        seen.add(forbidden)
        costs = [
            [limit if a == b or (a, b) in forbidden else distance[a][b] for b in range(size)]
            for a in range(size)
        ]
        bound, successor = hungarian(costs)
        if bound >= best_value:
            continue
        cycles = assignment_cycles(successor)
        if len(cycles) == 1:
            best, best_value = cycles[0], bound
        else:
            pivot = min(cycles, key=len)
            stack.extend(forbidden | {(u, successor[u])} for u in pivot)
    return best
