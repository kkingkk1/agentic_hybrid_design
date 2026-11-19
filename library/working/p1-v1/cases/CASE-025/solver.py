"""Sweep from several starting angles and solve short route orders exactly."""

from math import pi

from capacity_split import capacity_split
from fixed_path import fixed_path
from relocate import solution_length
from sweep_order import sweep_order


def solve(distance, demands, capacity, coordinates):
    if len(coordinates) != len(distance):
        raise ValueError("coordinates must provide a point for each vertex")
    best = None
    best_value = float("inf")
    for angle in (0.0, pi / 2, pi, 3 * pi / 2):
        groups = capacity_split(sweep_order(coordinates, angle), demands, capacity)
        routes = [
            fixed_path(distance, group, 0, 0) if len(group) <= 8 else group
            for group in groups
        ]
        value = solution_length(distance, routes)
        if value < best_value:
            best, best_value = routes, value
    return best
