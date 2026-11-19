"""Farthest insertion on a complete symmetric distance matrix."""


def farthest_insertion(distance, start=0):
    """Choose the vertex farthest from its closest tour vertex, then insert."""
    size = len(distance)
    if size == 0:
        return []
    if not 0 <= start < size:
        raise ValueError("start is outside the instance")
    tour = [start]
    nearest = {vertex: distance[start][vertex] for vertex in range(size) if vertex != start}
    while nearest:
        vertex = max(nearest, key=lambda node: (nearest[node], -node))
        edges = list(zip(tour, tour[1:] + tour[:1]))
        position = min(
            range(len(tour)),
            key=lambda i: (
                distance[edges[i][0]][vertex] + distance[vertex][edges[i][1]]
                - distance[edges[i][0]][edges[i][1]],
                i,
            ),
        )
        tour.insert(position + 1, vertex)
        del nearest[vertex]
        for other in nearest:
            nearest[other] = min(nearest[other], distance[vertex][other])
    return tour
