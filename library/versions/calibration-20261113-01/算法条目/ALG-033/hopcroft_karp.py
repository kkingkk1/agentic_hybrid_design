"""Hopcroft–Karp 二分图最大匹配。"""

from collections import deque


def hopcroft_karp(left_count, right_count, edges):
    """返回互不共享端点的最大匹配对，顶点采用零起始下标。"""
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (left_count, right_count)):
        raise ValueError("顶点数必须为非负整数")
    graph = [[] for _ in range(left_count)]
    for u, v in edges:
        if isinstance(u, bool) or not isinstance(u, int) or not 0 <= u < left_count or isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < right_count:
            raise ValueError("二分图边端点无效")
        graph[u].append(v)
    left, right = [-1] * left_count, [-1] * right_count
    while True:
        dist = [None] * left_count; queue = deque()
        for u in range(left_count):
            if left[u] == -1:
                dist[u] = 0; queue.append(u)
        limit = None
        while queue:
            u = queue.popleft()
            if limit is not None and dist[u] >= limit:
                continue
            for v in graph[u]:
                partner = right[v]
                if partner == -1:
                    limit = dist[u] + 1 if limit is None else min(limit, dist[u] + 1)
                elif dist[partner] is None:
                    dist[partner] = dist[u] + 1; queue.append(partner)
        if limit is None:
            break

        def augment(u):
            for v in graph[u]:
                partner = right[v]
                if (partner == -1 and dist[u] + 1 == limit) or (partner != -1 and dist[partner] == dist[u] + 1 and augment(partner)):
                    left[u], right[v] = v, u
                    return True
            dist[u] = None
            return False

        for u in range(left_count):
            if left[u] == -1 and dist[u] is not None:
                augment(u)
    return [(u, v) for u, v in enumerate(left) if v != -1]
