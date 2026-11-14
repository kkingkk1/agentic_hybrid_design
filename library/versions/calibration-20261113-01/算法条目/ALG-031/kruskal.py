"""无向图最小生成树的 Kruskal 算法。"""

from fractions import Fraction
from math import isfinite


def kruskal(n, edges):
    """返回总权重及树边；不连通返回 None，空图返回零和空边。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("顶点数必须为非负整数")
    prepared = []
    for index, (u, v, w) in enumerate(edges):
        if any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n for x in (u, v)):
            raise ValueError("边端点无效")
        if isinstance(w, bool) or not isinstance(w, (int, float)) or (isinstance(w, float) and not isfinite(w)):
            raise ValueError("边权须为有限数值")
        prepared.append((Fraction(w), index, u, v))
    parent = list(range(n)); rank = [0] * n
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    result = []; total = Fraction(0)
    for w, _, u, v in sorted(prepared):
        a, b = find(u), find(v)
        if a == b:
            continue
        if rank[a] < rank[b]: a, b = b, a
        parent[b] = a
        if rank[a] == rank[b]: rank[a] += 1
        result.append((u, v, w)); total += w
    return (total, result) if len(result) == max(n - 1, 0) else None
