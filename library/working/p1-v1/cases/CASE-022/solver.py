"""Anneal reversal moves, then polish the best tour with an Or-opt move."""

from random import Random

from annealing_acceptance import annealing_accept
from farthest_insertion import farthest_insertion
from nearest_tour import tour_length
from or_opt import or_opt


def solve(distance, seed=0, rounds=50):
    size = len(distance)
    current = farthest_insertion(distance)
    if size < 3:
        return current
    rng = Random(seed)
    current_value = tour_length(distance, current)
    best, best_value = current, current_value
    temperature = max(1.0, current_value / size)
    for _ in range(rounds):
        start, end = sorted(rng.sample(range(size), 2))
        trial = current[:start] + current[start:end + 1][::-1] + current[end + 1:]
        value = tour_length(distance, trial)
        if annealing_accept(current_value, value, temperature, rng):
            current, current_value = trial, value
            if value < best_value:
                best, best_value = trial, value
        temperature = max(1e-12, 0.95 * temperature)
    return or_opt(distance, best)
