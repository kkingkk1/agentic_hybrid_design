"""Global cheapest insertion for a complete matrix with zero diagonal."""


def cheapest_insertion(distance, start=0):
    """Return a vertex order without repeating the start."""
    size = len(distance)
    if size == 0:
        return []
    if not 0 <= start < size:
        raise ValueError("start is outside the instance")
    tour = [start]
    remaining = set(range(size)) - {start}
    while remaining:
        edges = list(zip(tour, tour[1:] + tour[:1]))
        _, vertex, position = min(
            (
                distance[left][vertex] + distance[vertex][right] - distance[left][right],
                vertex,
                index + 1,
            )
            for vertex in remaining
            for index, (left, right) in enumerate(edges)
        )
        tour.insert(position, vertex)
        remaining.remove(vertex)
    return tour
