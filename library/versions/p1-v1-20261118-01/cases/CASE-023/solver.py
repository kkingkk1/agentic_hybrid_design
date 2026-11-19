"""Try a lower-bound certificate before exact subset dynamic programming."""

from held_karp import held_karp
from nearest_tour import nearest_tour
from one_tree import one_tree
from two_opt import two_opt


def solve(distance):
    size = len(distance)
    if size > 12 or any(type(v) is not int or v < 0 for row in distance for v in row):
        raise ValueError("expected at most 12 vertices with nonnegative integer costs")
    if size < 3:
        return list(range(size))
    upper, tour = two_opt(nearest_tour(distance), distance)
    weights = [0] * size
    for step in (4, 4, 3, 3, 2, 2, 1, 1):
        lower, degree = one_tree(distance, weights)
        if lower == upper:
            return tour
        weights = [w + step * (d - 2) for w, d in zip(weights, degree)]
    _, closed = held_karp(distance)
    return closed[:-1]
