"""Shortcut a doubled tree walk by visiting each vertex at its first visit."""


def preorder_tour(size, edges, start=0):
    """Use undirected (u, v) edges spanning vertices 0 through size - 1."""
    edges = list(edges)
    if size == 0 and not edges:
        return []
    if len(edges) != size - 1 or not 0 <= start < size:
        raise ValueError("expected a spanning tree and a valid start")
    neighbors = [[] for _ in range(size)]
    for a, b in edges:
        if not 0 <= a < size or not 0 <= b < size or a == b:
            raise ValueError("invalid tree edge")
        neighbors[a].append(b)
        neighbors[b].append(a)
    order = []
    stack = [start]
    visited = set()
    while stack:
        vertex = stack.pop()
        if vertex not in visited:
            order.append(vertex)
            visited.add(vertex)
            stack.extend(sorted(neighbors[vertex], reverse=True))
    if len(order) != size:
        raise ValueError("tree does not span the instance")
    return order
