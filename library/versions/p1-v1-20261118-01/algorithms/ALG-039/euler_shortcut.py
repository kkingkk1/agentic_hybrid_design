"""Euler circuit construction and shortcutting for undirected multigraphs."""


def euler_shortcut(edges, start=0):
    """Return the first-visit order of a closed Euler walk from start."""
    adjacency = {}
    edges = list(edges)
    for index, (a, b) in enumerate(edges):
        if a == b:
            raise ValueError("an edge must connect distinct vertices")
        adjacency.setdefault(a, []).append((b, index))
        adjacency.setdefault(b, []).append((a, index))
    if not edges:
        return [start]
    if start not in adjacency or any(len(incident) % 2 for incident in adjacency.values()):
        raise ValueError("start must belong to an even-degree multigraph")

    stack = [start]
    walk = []
    used = set()
    while stack:
        incident = adjacency[stack[-1]]
        while incident and incident[-1][1] in used:
            incident.pop()
        if incident:
            other, index = incident.pop()
            used.add(index)
            stack.append(other)
        else:
            walk.append(stack.pop())
    if len(used) != len(edges):
        raise ValueError("multigraph is disconnected")
    return list(dict.fromkeys(reversed(walk)))
