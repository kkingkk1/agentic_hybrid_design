"""Capacity-feasible relocate moves between distinct CVRP routes."""

from math import fsum


def solution_length(distance, routes):
    """Sum all depot legs and internal arcs of a route set."""
    closed = [(0, *route, 0) for route in routes]
    costs = [distance[a][b] for route in closed for a, b in zip(route, route[1:])]
    return sum(costs) if all(type(value) is int for value in costs) else fsum(costs)


def route_length(distance, route):
    """Compute distance for a route with implicit depot 0 at both ends."""
    return solution_length(distance, [route])


def relocations(demands, capacity, routes):
    """Yield (routes, moved customer) for each feasible interroute move."""
    loads = [sum(demands[v] for v in route) for route in routes]
    for origin, source in enumerate(routes):
        for index, vertex in enumerate(source):
            for target, destination in enumerate(routes):
                if target == origin or loads[target] + demands[vertex] > capacity:
                    continue
                for position in range(len(destination) + 1):
                    candidate = [list(route) for route in routes]
                    candidate[origin].pop(index)
                    candidate[target].insert(position, vertex)
                    yield [route for route in candidate if route], vertex


def best_relocate(distance, demands, capacity, routes):
    """Choose a strict improvement by total distance, or return a copy."""
    best = [list(route) for route in routes]
    best_value = solution_length(distance, best)
    for candidate, _ in relocations(demands, capacity, routes):
        value = solution_length(distance, candidate)
        if value < best_value:
            best, best_value = candidate, value
    return best
