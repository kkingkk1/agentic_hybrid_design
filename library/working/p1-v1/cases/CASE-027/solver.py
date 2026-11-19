"""Use savings merges to seed strict capacity-aware relocate descent."""

from relocate import best_relocate, solution_length
from savings import savings_routes


def solve(distance, demands, capacity):
    incumbent = savings_routes(distance, demands, capacity)
    length = solution_length(distance, incumbent)
    while True:
        candidate = best_relocate(distance, demands, capacity, incumbent)
        value = solution_length(distance, candidate)
        if value >= length:
            return incumbent
        incumbent, length = candidate, value
