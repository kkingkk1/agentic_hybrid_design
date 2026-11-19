"""Compute a weighted minimum 1-tree bound for symmetric TSP."""

from heapq import nsmallest


def one_tree(distance, weights, root=0):
    """Return the Lagrangian bound and vertex degrees of a minimum 1-tree."""
    size = len(distance)
    if size < 3 or not 0 <= root < size or len(weights) != size:
        raise ValueError("expected at least three vertices, a root and a weight per vertex")

    def cost(a, b):
        return distance[a][b] + weights[a] + weights[b]

    others = [v for v in range(size) if v != root]
    start = others[0]
    cheapest = {v: (cost(start, v), start) for v in others[1:]}
    degree = [0] * size
    total = 0
    while cheapest:
        vertex = min(cheapest, key=lambda v: (cheapest[v], v))
        weight, parent = cheapest.pop(vertex)
        total += weight
        degree[vertex] += 1
        degree[parent] += 1
        for v in cheapest:
            cheapest[v] = min(cheapest[v], (cost(vertex, v), vertex))
    for weight, vertex in nsmallest(2, ((cost(root, v), v) for v in others)):
        total += weight
        degree[root] += 1
        degree[vertex] += 1
    return total - 2 * sum(weights), degree
