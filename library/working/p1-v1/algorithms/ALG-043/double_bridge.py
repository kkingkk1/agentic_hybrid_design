"""Four-cut double-bridge perturbation for open TSP tours."""


def double_bridge(tour, rng):
    """Reconnect four fragments, each with at least two vertices."""
    tour = list(tour)
    size = len(tour)
    if size < 8:
        return tour
    offset = rng.randrange(size)
    order = tour[offset:] + tour[:offset]
    bars = [-1, *sorted(rng.sample(range(size - 5), 3)), size - 5]
    fragments = []
    start = 0
    for left, right in zip(bars, bars[1:]):
        end = start + right - left + 1
        fragments.append(order[start:end])
        start = end
    first, second, third, fourth = fragments
    return first + fourth + third + second
