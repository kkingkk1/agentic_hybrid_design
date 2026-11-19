"""Route fixed-seed generalized assignment clusters."""

from fixed_path import fixed_path
from savings import savings_routes
from seeded_assignment import seeded_assignment


def solve(distance, demands, capacity, seeds):
    if len(distance) > 12:
        raise ValueError("reference assignment is limited to 11 customers")
    groups = seeded_assignment(distance, demands, capacity, seeds)
    if groups is None:
        return savings_routes(distance, demands, capacity)
    return [
        fixed_path(distance, group, 0, 0) if len(group) <= 8 else group
        for group in groups
    ]
