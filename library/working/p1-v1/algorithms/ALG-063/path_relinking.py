"""Directed swap path between permutations with identical vertex sets."""


def path_relink(start, target):
    """Yield new orders whose matching prefix with target grows at each swap."""
    if len(start) != len(target) or len(set(start)) != len(start) or set(start) != set(target):
        raise ValueError("endpoints must permute the same unique vertices")
    order = list(start)
    positions = {vertex: index for index, vertex in enumerate(order)}
    for index, vertex in enumerate(target):
        other_index = positions[vertex]
        if other_index == index:
            continue
        other = order[index]
        order[index], order[other_index] = vertex, other
        positions[vertex], positions[other] = index, other_index
        yield list(order)
