"""可含负边的 Bellman–Ford 单源最短路径。"""

from fractions import Fraction
from math import isfinite


def bellman_ford(n, edges, source):
    """返回距离和前驱；起点可达负环时报错，不可达顶点为 None。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or isinstance(source, bool) or not isinstance(source, int) or not 0 <= source < n:
        raise ValueError("顶点数或起点无效")
    prepared = []
    for u, v, w in edges:
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (u, v)):
            raise ValueError("边端点无效")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or (isinstance(w, float) and not isfinite(w)):
            raise ValueError("边权须为有限数值")
        prepared.append((u, v, Fraction(w)))
    distance, predecessor = [None] * n, [None] * n
    distance[source] = Fraction(0)
    for _ in range(n - 1):
        changed = False
        for u, v, weight in prepared:
            if distance[u] is not None and (distance[v] is None or distance[u] + weight < distance[v]):
                distance[v], predecessor[v] = distance[u] + weight, u
                changed = True
        if not changed:
            break
    if any(distance[u] is not None and (distance[v] is None or distance[u] + w < distance[v]) for u, v, w in prepared):
        raise ValueError("起点可达负权环")
    return distance, predecessor
