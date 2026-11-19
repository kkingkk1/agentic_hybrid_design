"""Best improving 3-edge reconnection for a symmetric TSP tour."""

from math import fsum


def three_opt(distance, tour):
    """Return one best move, or a copy of tour if no move reduces its length."""
    tour = list(tour)
    size = len(tour)
    if size < 6:
        return tour

    def cost(order):
        costs = [distance[a][b] for a, b in zip(order, order[1:] + order[:1])]
        return sum(costs) if all(type(value) is int for value in costs) else fsum(costs)

    best = tour
    best_cost = cost(tour)
    for first in range(size - 4):
        for second in range(first + 2, size - 2):
            for third in range(second + 2, size):
                if first == 0 and third == size - 1:
                    continue
                fixed = tour[third + 1:] + tour[:first + 1]
                a = tour[first + 1:second + 1]
                b = tour[second + 1:third + 1]
                for left, right in ((a, b), (b, a)):
                    for start in (left, left[::-1]):
                        for end in (right, right[::-1]):
                            candidate = fixed + start + end
                            value = cost(candidate)
                            if value < best_cost:
                                best, best_cost = candidate, value
    return best
