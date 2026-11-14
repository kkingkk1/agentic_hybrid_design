"""非负有向边权的 Dijkstra 单源最短路径。"""

from fractions import Fraction
from heapq import heappop, heappush
from math import isfinite


def dijkstra(n, edges, source):
    """返回距离和前驱列表；不可达顶点为 None。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or isinstance(source, bool) or not isinstance(source, int) or not 0 <= source < n:
        raise ValueError("顶点数或起点无效")
    graph = [[] for _ in range(n)]
    for u, v, w in edges:
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (u, v)):
            raise ValueError("边端点无效")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0 or (isinstance(w, float) and not isfinite(w)):
            raise ValueError("边权须为有限非负数")
        graph[u].append((v, Fraction(w)))
    distance, predecessor = [None] * n, [None] * n
    distance[source] = Fraction(0)
    queue = [(Fraction(0), source)]
    while queue:
        cost, u = heappop(queue)
        if cost != distance[u]:
            continue
        for v, weight in graph[u]:
            candidate = cost + weight
            if distance[v] is None or candidate < distance[v]:
                distance[v], predecessor[v] = candidate, u
                heappush(queue, (candidate, v))
    return distance, predecessor
