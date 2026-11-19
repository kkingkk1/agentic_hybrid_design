"""Cyclic edge recombination crossover for two TSP parents."""


def edge_recombine(first, second, rng):
    """Prefer an unused parental neighbor having few remaining edges."""
    if len(first) != len(second) or set(first) != set(second) or len(set(first)) != len(first):
        raise ValueError("parents must permute the same unique vertices")
    if not first:
        return []
    adjacent = {vertex: set() for vertex in first}
    for parent in (first, second):
        for index, vertex in enumerate(parent):
            adjacent[vertex].update((parent[index - 1], parent[(index + 1) % len(parent)]))
    remaining = set(first)
    tour = []
    vertex = first[0]
    while remaining:
        tour.append(vertex)
        remaining.remove(vertex)
        for neighbor in adjacent[vertex]:
            if neighbor != vertex:
                adjacent[neighbor].discard(vertex)
        choices = adjacent[vertex] & remaining
        if choices:
            degree = min(len(adjacent[node]) for node in choices)
            eligible = sorted(node for node in choices if len(adjacent[node]) == degree)
            vertex = rng.choice(eligible)
        elif remaining:
            vertex = rng.choice(sorted(remaining))
    return tour
