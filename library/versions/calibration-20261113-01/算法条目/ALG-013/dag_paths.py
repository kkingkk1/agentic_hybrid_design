"""有向无环图的拓扑序最短路径。"""

from collections import deque
from fractions import Fraction
from math import isfinite


def dag_shortest_paths(n, edges, source):
    """返回各点距离和前驱；不可达点为 None，可包含负边。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("顶点数必须为正整数")
    if isinstance(source, bool) or not isinstance(source, int) or not 0 <= source < n:
        raise ValueError("起点无效")
    neighbors = [[] for _ in range(n)]
    indegree = [0] * n
    for u, v, w in edges:
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (u, v)):
            raise ValueError("边端点无效")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or (isinstance(w, float) and not isfinite(w)):
            raise ValueError("边权须为有限数值")
        neighbors[u].append((v, Fraction(w)))
        indegree[v] += 1
    queue = deque(i for i, degree in enumerate(indegree) if degree == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v, _ in neighbors[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if len(order) != n:
        raise ValueError("输入图不是有向无环图")
    distance, predecessor = [None] * n, [None] * n
    distance[source] = Fraction(0)
    for u in order:
        if distance[u] is None:
            continue
        for v, weight in neighbors[u]:
            value = distance[u] + weight
            if distance[v] is None or value < distance[v]:
                distance[v], predecessor[v] = value, u
    return distance, predecessor
