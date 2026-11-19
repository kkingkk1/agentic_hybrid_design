"""Generate capacity-feasible polar petals and choose a disjoint cover."""

from fixed_path import fixed_path
from route_partition import partition_routes
from sweep_order import sweep_order


def solve(distance, demands, capacity, coordinates):
    if len(distance) > 13 or len(distance) != len(coordinates):
        raise ValueError("expected matching coordinates for at most 12 customers")
    order = sweep_order(coordinates)
    if capacity < 0 or any(not 0 <= demands[v] <= capacity for v in order):
        raise ValueError("customer cannot be served by a singleton route")
    pool = []
    for start in range(len(order)):
        traversal = order[start:] + order[:start]
        load = 0
        for stop, vertex in enumerate(traversal, 1):
            load += demands[vertex]
            if load > capacity:
                break
            group = traversal[:stop]
            pool.append(fixed_path(distance, group, 0, 0) if stop <= 8 else group)
    return partition_routes(distance, order, pool)
