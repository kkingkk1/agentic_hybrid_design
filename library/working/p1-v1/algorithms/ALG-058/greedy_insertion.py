"""Deterministic least-cost feasible insertion for capacitated routes."""


def best_insertion(distance, demands, capacity, route, vertex):
    """Return (distance delta, updated route) or None for capacity failure."""
    if sum(demands[v] for v in route) + demands[vertex] > capacity:
        return None
    closed = [0, *route, 0]
    delta, position = min(
        (distance[a][vertex] + distance[vertex][b] - distance[a][b], index)
        for index, (a, b) in enumerate(zip(closed, closed[1:]))
    )
    result = list(route)
    result.insert(position, vertex)
    return delta, result


def greedy_insert(distance, demands, capacity, routes, customers, *, existing_only=False):
    """Insert customers in order, opening a singleton only if permitted and needed."""
    routes = [list(route) for route in routes if route]
    customers = list(customers)
    vertices = [v for route in routes for v in route] + customers
    if len(set(vertices)) != len(vertices) or any(not 0 < v < len(distance) for v in vertices):
        raise ValueError("routes and customers must partition distinct nondepot vertices")
    if capacity < 0 or any(not 0 <= demands[v] <= capacity for v in vertices):
        raise ValueError("customer cannot be served by a singleton route")
    if any(sum(demands[v] for v in route) > capacity for route in routes):
        raise ValueError("input routes exceed capacity")
    for vertex in customers:
        options = []
        for index, route in enumerate(routes):
            trial = best_insertion(distance, demands, capacity, route, vertex)
            if trial is not None:
                options.append((trial[0], index, trial[1]))
        if options:
            _, index, route = min(options)
            routes[index] = route
        elif existing_only:
            return None
        else:
            routes.append([vertex])
    return routes
