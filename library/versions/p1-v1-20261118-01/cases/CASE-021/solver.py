"""Update penalties on expensive used arcs after augmented local descent."""

from cheapest_insertion import cheapest_insertion
from nearest_tour import tour_length
from two_opt import two_opt


def solve(distance, rounds=10):
    size = len(distance)
    if size < 3:
        return list(range(size))
    _, current = two_opt(cheapest_insertion(distance), distance)
    best, best_value = current, tour_length(distance, current)
    scale = 0.1 * best_value / size
    penalties = [[0] * size for _ in range(size)]
    for _ in range(rounds):
        adjusted = [
            [distance[a][b] + scale * penalties[a][b] for b in range(size)]
            for a in range(size)
        ]
        _, trial = two_opt(current, adjusted)
        current = trial
        value = tour_length(distance, current)
        if value < best_value:
            best, best_value = current, value

        edges = list(zip(current, current[1:] + current[:1]))
        utilities = [distance[a][b] / (1 + penalties[a][b]) for a, b in edges]
        peak = max(utilities)
        for (a, b), utility in zip(edges, utilities):
            if utility == peak:
                penalties[a][b] += 1
                penalties[b][a] += 1
    return best
