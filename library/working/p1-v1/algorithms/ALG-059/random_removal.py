"""Uniform CVRP customer removal without replacement."""


def uniform_remove(routes, count, rng):
    """Return partial routes and the removed customers in sampled order."""
    customers = [v for route in routes for v in route]
    if len(set(customers)) != len(customers) or not 0 <= count <= len(customers):
        raise ValueError("expected distinct customers and a valid count")
    removed = rng.sample(customers, count)
    removed_set = set(removed)
    partial = [[v for v in route if v not in removed_set] for route in routes]
    return [route for route in partial if route], removed
