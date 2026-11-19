"""Solve very small CVRP by enumerating all feasible customer sets."""

from fixed_path import optimal_cvrp_routes
from route_partition import partition_routes


def solve(distance, demands, capacity):
    if len(distance) > 10 or any(type(value) is not int or value < 0 for row in distance for value in row):
        raise ValueError("expected at most 9 customers with nonnegative integer costs")
    routes = optimal_cvrp_routes(distance, demands, capacity)
    return partition_routes(distance, range(1, len(distance)), routes)
