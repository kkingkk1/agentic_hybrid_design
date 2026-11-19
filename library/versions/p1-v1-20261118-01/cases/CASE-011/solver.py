"""Accept strict improvements between locally optimized TSP tours."""

from random import Random

from double_bridge import double_bridge
from nearest_tour import nearest_tour
from two_opt import two_opt


def solve(distance, seed=0, rounds=12):
    rng = Random(seed)
    length, incumbent = two_opt(nearest_tour(distance), distance)
    for _ in range(rounds):
        shaken = double_bridge(incumbent, rng)
        trial_length, trial = two_opt(shaken, distance)
        if trial_length < length:
            length, incumbent = trial_length, trial
    return incumbent
