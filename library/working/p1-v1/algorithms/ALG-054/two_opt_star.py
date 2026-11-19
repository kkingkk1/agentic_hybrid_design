"""Interroute 2-opt* exchanges suffixes without reversing them."""

from itertools import accumulate


def tail_exchanges(demands, capacity, routes):
    """Yield all feasible tail exchanges between two distinct routes."""
    for i, route in enumerate(routes):
        first = list(route)
        first_prefix = list(accumulate((demands[v] for v in first), initial=0))
        for j in range(i + 1, len(routes)):
            second = list(routes[j])
            second_prefix = list(accumulate((demands[v] for v in second), initial=0))
            for a in range(len(first) + 1):
                for b in range(len(second) + 1):
                    if (a, b) in ((0, 0), (len(first), len(second))):
                        continue
                    load_a = first_prefix[a] + second_prefix[-1] - second_prefix[b]
                    load_b = second_prefix[b] + first_prefix[-1] - first_prefix[a]
                    if max(load_a, load_b) <= capacity:
                        candidate = [list(route) for route in routes]
                        candidate[i] = first[:a] + second[b:]
                        candidate[j] = second[:b] + first[a:]
                        yield [route for route in candidate if route]


def two_opt_star(distance, demands, capacity, routes):
    """Return a best strict improvement in the feasible tail neighborhood."""
    def cost(solution):
        total = 0
        for route in solution:
            closed = [0, *route, 0]
            total += sum(distance[a][b] for a, b in zip(closed, closed[1:]))
        return total

    best = [list(route) for route in routes]
    best_cost = cost(best)
    for candidate in tail_exchanges(demands, capacity, routes):
        value = cost(candidate)
        if value < best_cost:
            best, best_cost = candidate, value
    return best
