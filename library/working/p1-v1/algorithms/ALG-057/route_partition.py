"""Exact small restricted route set partitioning by subset DP."""

from functools import cache


def partition_routes(distance, customers, pool):
    """Return a minimum-cost disjoint cover from the supplied routes, or None."""
    customers = sorted(customers)
    if len(set(customers)) != len(customers) or any(not 0 < v < len(distance) for v in customers):
        raise ValueError("customers must be distinct nondepot vertices")
    bits = {v: 1 << index for index, v in enumerate(customers)}
    columns = {}
    for path in pool:
        route = tuple(path)
        if not route or len(set(route)) != len(route) or not set(route) <= bits.keys():
            raise ValueError("a route must visit distinct known customers")
        mask = sum(bits[v] for v in route)
        closed = (0, *route, 0)
        length = sum(distance[a][b] for a, b in zip(closed, closed[1:]))
        candidate = length, route
        if mask not in columns or candidate < columns[mask]:
            columns[mask] = candidate
    choices = {
        bit: [mask for mask in columns if mask & bit]
        for bit in bits.values()
    }

    @cache
    def cover(remaining):
        if remaining == 0:
            return 0, ()
        pivot = remaining & -remaining
        best = None
        for mask in choices[pivot]:
            if mask & remaining != mask:
                continue
            suffix = cover(remaining ^ mask)
            if suffix is None:
                continue
            length, route = columns[mask]
            candidate = length + suffix[0], (route, *suffix[1])
            if best is None or candidate < best:
                best = candidate
        return best

    answer = cover((1 << len(customers)) - 1)
    return None if answer is None else [list(route) for route in answer[1]]
