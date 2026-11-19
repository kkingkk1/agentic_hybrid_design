"""Revisit the first neighborhood after each improvement in CVRP VND."""

from capacity_split import capacity_split
from cross_exchange import cross_exchange
from relocate import best_relocate, solution_length
from two_opt_star import two_opt_star


def solve(distance, demands, capacity):
    incumbent = capacity_split(range(1, len(distance)), demands, capacity)
    value = solution_length(distance, incumbent)
    moves = (two_opt_star, cross_exchange, best_relocate)
    index = 0
    while index < len(moves):
        trial = moves[index](distance, demands, capacity, incumbent)
        length = solution_length(distance, trial)
        if length < value:
            incumbent, value, index = trial, length, 0
        else:
            index += 1
    return incumbent
