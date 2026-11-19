"""有限深度的迭代加深深度优先搜索。"""


def iterative_deepening(graph, start, goal, max_depth):
    """在显式有限有向图中返回最少边数路径；超过深度上限返回 None。"""
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("深度上限必须为非负整数")

    def visit(node, remaining, path, on_path):
        if node == goal:
            return path
        if remaining == 0:
            return None
        for nxt in graph.get(node, ()):
            if nxt not in on_path:
                result = visit(nxt, remaining - 1, [*path, nxt], on_path | {nxt})
                if result is not None:
                    return result
        return None

    for limit in range(max_depth + 1):
        result = visit(start, limit, [start], {start})
        if result is not None:
            return result
    return None
