"""整数容量网络的 Edmonds–Karp 最大流与最小割。"""

from collections import deque


def edmonds_karp(n, edges, source, sink):
    """返回最大流值及残量网络中源点可达的割一侧。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 2:
        raise ValueError("顶点数必须至少为 2")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (source, sink)) or source == sink:
        raise ValueError("源点和汇点必须是不同有效顶点")
    residual = [[0] * n for _ in range(n)]
    for u, v, capacity in edges:
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (u, v)):
            raise ValueError("边端点无效")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ValueError("容量必须为非负整数")
        residual[u][v] += capacity
    value = 0
    while True:
        parent = [None] * n; parent[source] = source; queue = deque([source])
        while queue and parent[sink] is None:
            u = queue.popleft()
            for v in range(n):
                if residual[u][v] > 0 and parent[v] is None:
                    parent[v] = u; queue.append(v)
        if parent[sink] is None:
            return value, frozenset(i for i, p in enumerate(parent) if p is not None)
        amount, v = None, sink
        while v != source:
            u = parent[v]; amount = residual[u][v] if amount is None else min(amount, residual[u][v]); v = u
        v = sink
        while v != source:
            u = parent[v]; residual[u][v] -= amount; residual[v][u] += amount; v = u
        value += amount
