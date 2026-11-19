"""Replace only a selected pair of geographically related routes."""

from relocate import best_relocate, solution_length
from savings import savings_routes
from two_opt_star import two_opt_star


def solve(distance, demands, capacity, rounds=10):
    routes = savings_routes(distance, demands, capacity)
    for step in range(rounds):
        if len(routes) < 2:
            break
        anchor = step % len(routes)
        neighbor = min(
            (index for index in range(len(routes)) if index != anchor),
            key=lambda index: (
                min(distance[a][b] for a in routes[anchor] for b in routes[index]),
                index,
            ),
        )
        paired = [routes[anchor], routes[neighbor]]
        subset = paired[0] + paired[1]
        reoptimized = savings_routes(distance, demands, capacity, customers=subset)
        reoptimized = best_relocate(distance, demands, capacity, reoptimized)
        reoptimized = two_opt_star(distance, demands, capacity, reoptimized)
        if solution_length(distance, reoptimized) < solution_length(distance, paired):
            routes = [
                route for index, route in enumerate(routes) if index not in (anchor, neighbor)
            ] + reoptimized
    return routes
