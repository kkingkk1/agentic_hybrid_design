"""Greedy capacitated decoding of a fixed giant-tour order."""


def capacity_split(order, demands, capacity):
    """Return consecutive capacity-feasible routes using maximal prefixes."""
    order = list(order)
    if len(set(order)) != len(order):
        raise ValueError("order contains duplicate customers")
    if capacity < 0 or any(
        not 0 < v < len(demands) or not 0 <= demands[v] <= capacity for v in order
    ):
        raise ValueError("customer cannot be served by a singleton route")
    routes = []
    route = []
    load = 0
    for vertex in order:
        demand = demands[vertex]
        if route and load + demand > capacity:
            routes.append(route)
            route, load = [], 0
        route.append(vertex)
        load += demand
    if route:
        routes.append(route)
    return routes
