"""Improve a doubled-tree shortcut tour by symmetric 2-opt."""

from kruskal import kruskal
from tree_preorder import preorder_tour
from two_opt import two_opt


def solve(distance):
    size = len(distance)
    if size < 2:
        return list(range(size))
    _, tree = kruskal(
        size, [(a, b, distance[a][b]) for a in range(size) for b in range(a + 1, size)]
    )
    tour = preorder_tour(size, [(a, b) for a, b, _ in tree])
    return two_opt(tour, distance)[1]
