"""Exact minimum-weight perfect matching on a small even complete graph."""

from functools import cache


def minimum_matching(distance, vertices):
    """Return disjoint vertex pairs of minimum total weight."""
    vertices = tuple(vertices)
    if len(vertices) % 2 or len(set(vertices)) != len(vertices):
        raise ValueError("expected an even set of distinct vertices")
    if any(not 0 <= v < len(distance) for v in vertices):
        raise ValueError("matching vertex is outside the instance")

    @cache
    def match(mask):
        if mask == 0:
            return 0, ()
        first_bit = mask & -mask
        a = vertices[first_bit.bit_length() - 1]
        rest = mask ^ first_bit
        alternatives = rest
        best = None
        while alternatives:
            bit = alternatives & -alternatives
            b = vertices[bit.bit_length() - 1]
            weight, pairs = match(rest ^ bit)
            candidate = distance[a][b] + weight, ((a, b),) + pairs
            if best is None or candidate < best:
                best = candidate
            alternatives ^= bit
        return best

    _, pairs = match((1 << len(vertices)) - 1)
    return list(pairs)
