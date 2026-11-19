"""Reinforce edges of ant tours after local search."""

from random import Random

from ant_system import ant_system
from three_opt import three_opt
from two_opt import two_opt


def solve(distance, seed=0, rounds=6):
    def polish(tour):
        _, local = two_opt(tour, distance)
        candidate = three_opt(distance, local)
        return two_opt(candidate, distance)[1]

    return ant_system(distance, steps=rounds, ants=4, rng=Random(seed), improve=polish)
