"""Nearest-neighbor construction for a complete distance matrix."""

from math import fsum


def tour_length(distance, tour):
    """Compute cycle length with an implicit return edge."""
    costs = [distance[a][b] for a, b in zip(tour, tour[1:] + tour[:1])]
    return sum(costs) if all(type(value) is int for value in costs) else fsum(costs)


def nearest_tour(distance, start=0):
    """Return an open tour. Joining the last vertex to the first closes it."""
    size = len(distance)
    if size == 0:
        return []
    if not 0 <= start < size:
        raise ValueError("start is outside the instance")
    tour = [start]
    remaining = set(range(size)) - {start}
    while remaining:
        last = tour[-1]
        vertex = min(remaining, key=lambda node: (distance[last][node], node))
        tour.append(vertex)
        remaining.remove(vertex)
    return tour
