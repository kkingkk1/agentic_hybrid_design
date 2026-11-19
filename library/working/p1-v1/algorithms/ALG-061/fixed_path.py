"""Exact small route segment reorder with fixed incoming and outgoing vertices."""

from functools import cache
from itertools import combinations


def fixed_path(distance, block, before, after):
    """Return an optimal order of block between fixed endpoints."""
    block = tuple(block)
    vertices = (*block, before, after)
    if any(not 0 <= vertex < len(distance) for vertex in vertices):
        raise ValueError("vertex is outside the instance")
    if len(set(block)) != len(block) or before in block or after in block:
        raise ValueError("block must contain distinct internal vertices")

    @cache
    def suffix(current, mask):
        if mask == 0:
            return distance[current][after], ()
        best = None
        available = mask
        while available:
            bit = available & -available
            following = block[bit.bit_length() - 1]
            length, tail = suffix(following, mask ^ bit)
            candidate = distance[current][following] + length, (following, *tail)
            if best is None or candidate < best:
                best = candidate
            available ^= bit
        return best

    return list(suffix(before, (1 << len(block)) - 1)[1])


def optimal_cvrp_routes(distance, demands, capacity):
    """Yield a least-cost depot tour for each nonempty feasible customer set."""
    customers = range(1, len(distance))
    if capacity < 0 or any(not 0 <= demands[v] <= capacity for v in customers):
        raise ValueError("customer cannot be served by a singleton route")
    for count in range(1, len(customers) + 1):
        for group in combinations(customers, count):
            if sum(demands[v] for v in group) <= capacity:
                yield fixed_path(distance, group, 0, 0)
