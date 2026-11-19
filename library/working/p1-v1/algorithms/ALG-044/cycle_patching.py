"""Merge cycles of an assignment by exchanging two successor arcs."""


def assignment_cycles(successor):
    """Decompose a successor permutation into lists of vertices."""
    if sorted(successor) != list(range(len(successor))):
        raise ValueError("successor must be a permutation")
    seen = set()
    cycles = []
    for start in range(len(successor)):
        if start in seen:
            continue
        cycle = []
        vertex = start
        while vertex not in seen:
            seen.add(vertex)
            cycle.append(vertex)
            vertex = successor[vertex]
        cycles.append(cycle)
    return cycles


def patch_cycles(distance, successor):
    """Return an open TSP tour by greedily joining different cycles."""
    successor = list(successor)
    cycles = assignment_cycles(successor)
    while len(cycles) > 1:
        _, a, b = min(
            (
                distance[u][successor[v]] + distance[v][successor[u]]
                - distance[u][successor[u]] - distance[v][successor[v]],
                u,
                v,
            )
            for i, first in enumerate(cycles)
            for second in cycles[i + 1:]
            for u in first
            for v in second
        )
        successor[a], successor[b] = successor[b], successor[a]
        cycles = assignment_cycles(successor)
    return cycles[0] if cycles else []
