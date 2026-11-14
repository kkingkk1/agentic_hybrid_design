"""固定宽度的分层束搜索。"""

from math import isfinite


def beam_search(graph, start, goal, width, max_depth, heuristic):
    """每层只保留启发值最小的 width 条无环路径；可能漏解。"""
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (width, max_depth)) or width < 1 or max_depth < 0:
        raise ValueError("束宽须为正整数，深度上限须为非负整数")
    frontier = [(start,)]
    for depth in range(max_depth + 1):
        for path in frontier:
            if path[-1] == goal:
                return list(path)
        if depth == max_depth:
            break
        candidates = []
        for path in frontier:
            for nxt in graph.get(path[-1], ()):
                if nxt in path:
                    continue
                score = heuristic(nxt)
                if isinstance(score, bool) or not isinstance(score, (int, float)) or (isinstance(score, float) and not isfinite(score)):
                    raise ValueError("启发值必须为有限数值")
                candidates.append((score, (*path, nxt)))
        candidates.sort(key=lambda item: item[0])
        frontier = [path for _, path in candidates[:width]]
        if not frontier:
            break
    return None
