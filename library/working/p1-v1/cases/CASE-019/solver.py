"""Change the shake size after failure and reset it after improvement."""

from random import Random

from cheapest_insertion import cheapest_insertion
from nearest_tour import tour_length
from or_opt import or_opt
from two_opt import two_opt


def solve(distance, seed=0, rounds=12):
    size = len(distance)
    if size < 3:
        return list(range(size))
    rng = Random(seed)

    def descent(tour):
        length, candidate = two_opt(tour, distance)
        while True:
            moved = or_opt(distance, candidate)
            if tour_length(distance, moved) >= tour_length(distance, candidate):
                return length, candidate
            length, candidate = two_opt(moved, distance)

    best_value, best = descent(cheapest_insertion(distance))
    maximum = min(4, size)
    strength = 2
    for _ in range(rounds):
        candidate = list(best)
        indices = rng.sample(range(size), strength)
        for a, b in zip(indices, indices[1:] + indices[:1]):
            candidate[a] = best[b]
        value, trial = descent(candidate)
        if value < best_value:
            best_value, best, strength = value, trial, 2
        else:
            strength = 2 if strength == maximum else strength + 1
    return best
