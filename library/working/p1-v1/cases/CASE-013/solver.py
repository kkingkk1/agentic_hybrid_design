"""Construct a metric TSP tour using a tree and a parity correction."""

from euler_shortcut import euler_shortcut
from kruskal import kruskal
from perfect_matching import minimum_matching


def solve(distance):
    size = len(distance)
    if size < 3:
        return list(range(size))
    _, tree = kruskal(
        size, [(a, b, distance[a][b]) for a in range(size) for b in range(a + 1, size)]
    )
    degree = [0] * size
    for a, b, _ in tree:
        degree[a] += 1
        degree[b] += 1
    odd = [v for v, value in enumerate(degree) if value % 2]
    if len(odd) > 16:
        raise ValueError("reference matching is limited to 16 odd vertices")
    edges = [(a, b) for a, b, _ in tree] + minimum_matching(distance, odd)
    return euler_shortcut(edges)
