"""Use LP dual prices to grow a small route pool before integer recombination."""

from fixed_path import optimal_cvrp_routes
from primal_simplex import primal_simplex
from relocate import route_length
from route_partition import partition_routes


def solve(distance, demands, capacity):
    if len(distance) > 9 or any(type(v) is not int or v < 0 for row in distance for v in row):
        raise ValueError("expected at most 8 customers with nonnegative integer costs")
    customers = range(1, len(distance))
    if not customers:
        return []
    costs = {
        tuple(route): route_length(distance, route)
        for route in optimal_cvrp_routes(distance, demands, capacity)
    }
    pool = [(v,) for v in customers]
    known = set(pool)
    while True:
        incidence = [[int(v in route) for v in customers] for route in pool]
        status, _, prices = primal_simplex(incidence, [costs[r] for r in pool], [1] * len(customers))
        if status != "optimal":
            raise RuntimeError("singleton routes must bound every customer price")
        choice = min(
            (
                (length - sum(prices[v - 1] for v in route), route)
                for route, length in costs.items()
                if route not in known
            ),
            default=None,
        )
        if choice is None or choice[0] >= 0:
            break
        pool.append(choice[1])
        known.add(choice[1])
    return partition_routes(distance, customers, pool)
