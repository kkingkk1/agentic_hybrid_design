"""Or-opt moves a consecutive block within a tour without reversing it."""

from math import fsum


def or_opt(distance, tour, max_block=3):
    """Return the best strict improvement across cyclic blocks up to max_block."""
    if max_block < 1:
        raise ValueError("max_block must be positive")
    order = list(tour)
    size = len(order)

    def cost(path):
        costs = [distance[a][b] for a, b in zip(path, path[1:] + path[:1])]
        return sum(costs) if all(type(value) is int for value in costs) else fsum(costs)

    best = order
    best_cost = cost(order)
    for start in range(size):
        rotated = order[start:] + order[:start]
        for count in range(1, min(max_block, size - 2) + 1):
            block, remainder = rotated[:count], rotated[count:]
            for pos in range(1, len(remainder)):
                candidate = remainder[:pos] + block + remainder[pos:]
                value = cost(candidate)
                if value < best_cost:
                    best, best_cost = candidate, value
    return best
