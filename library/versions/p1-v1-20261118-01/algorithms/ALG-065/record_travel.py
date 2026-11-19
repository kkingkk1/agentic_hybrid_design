"""Record-to-record travel control with a fixed absolute deviation."""


def record_travel(initial, propose, cost, rounds, tolerance, rng):
    """Accept relative to the best record; return the cheapest solution seen."""
    if tolerance < 0 or rounds < 0:
        raise ValueError("tolerance and rounds must be nonnegative")
    current = best = initial
    record = cost(initial)
    for _ in range(rounds):
        candidate = propose(current, rng)
        if candidate is None:
            break
        value = cost(candidate)
        if value < record:
            best, record = candidate, value
        if value <= record + tolerance:
            current = candidate
    return best
