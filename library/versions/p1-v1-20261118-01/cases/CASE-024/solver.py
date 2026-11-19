"""Build one customer order, decode it under hard capacity, then relocate."""

from capacity_split import capacity_split
from nearest_tour import nearest_tour
from relocate import best_relocate


def solve(distance, demands, capacity):
    order = nearest_tour(distance, start=0)[1:]
    routes = capacity_split(order, demands, capacity)
    return best_relocate(distance, demands, capacity, routes)
