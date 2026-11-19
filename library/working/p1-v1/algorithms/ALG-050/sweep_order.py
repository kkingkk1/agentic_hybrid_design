"""Polar-angle ordering around the depot for geometric route clustering."""

from math import atan2, tau


def sweep_order(coordinates, start_angle=0.0):
    """Return nondepot vertices ordered by angle from start_angle."""
    if len(coordinates) <= 1:
        return []
    x0, y0 = coordinates[0]
    return sorted(
        range(1, len(coordinates)),
        key=lambda vertex: (
            (atan2(coordinates[vertex][1] - y0, coordinates[vertex][0] - x0) - start_angle) % tau,
            vertex,
        ),
    )
