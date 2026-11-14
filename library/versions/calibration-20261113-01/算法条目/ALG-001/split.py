"""固定客户顺序下，硬容量且车辆数不限的线性 Split。"""

from collections import deque
from fractions import Fraction
from math import isfinite
from typing import Sequence


def split_hard_capacity(
    demands: Sequence[int | float],
    capacity: int | float,
    from_depot: Sequence[int | float],
    to_depot: Sequence[int | float],
    between: Sequence[int | float],
) -> tuple[int | float, list[tuple[int, int]]] | None:
    """返回最小距离与路线区间；无硬容量可行划分时返回 None。

    各数组按给定客户顺序排列。between[i] 为第 i 个客户到第 i+1 个
    客户的距离；两组仓库距离分别表示仓库到客户、客户到仓库。
    路线用零起始、左闭右开的客户位置区间表示。
    需求、容量和距离必须是有限非负数；不限制距离对称性。
    浮点输入按其二进制值精确运算；含浮点距离时输出距离转回浮点数。
    按十进制精度判定时，需求和容量须按相同倍率缩放为整数；距离可另行缩放。
    不处理车辆数上限、软容量罚项、时间窗或其他约束。
    """
    n = len(demands)
    if len(from_depot) != n or len(to_depot) != n or len(between) != max(0, n - 1):
        raise ValueError("输入数组长度与客户数量不一致")

    def check(value: int | float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("需求、容量和距离必须是数值")
        if value < 0 or (isinstance(value, float) and not isfinite(value)):
            raise ValueError("需求、容量和距离必须是有限非负数")

    check(capacity)
    for values in (demands, from_depot, to_depot, between):
        for value in values:
            check(value)

    # 按输入浮点数的精确二进制值运算，避免前缀相减丢失需求或距离。
    def exact(values: Sequence[int | float]) -> list[int | Fraction]:
        return [Fraction(value) if isinstance(value, float) else value for value in values]

    exact_demands = exact(demands)
    exact_capacity = Fraction(capacity) if isinstance(capacity, float) else capacity
    exact_from = exact(from_depot)
    exact_to = exact(to_depot)
    exact_between = exact(between)
    float_distance = any(isinstance(v, float) for seq in (from_depot, to_depot, between) for v in seq)
    load: list[int | Fraction] = [0] * (n + 1)
    distance: list[int | Fraction] = [0] * (n + 1)
    for i in range(1, n + 1):
        load[i] = load[i - 1] + exact_demands[i - 1]
        if i > 1:
            distance[i] = distance[i - 1] + exact_between[i - 2]

    best: list[int | Fraction | None] = [None] * (n + 1)
    pred = [-1] * (n + 1)
    key: list[int | Fraction] = [0] * n
    candidates: deque[int] = deque()
    best[0] = 0

    for end in range(1, n + 1):
        start = end - 1
        if best[start] is not None:
            key[start] = best[start] + exact_from[start] - distance[start + 1]
            while candidates and key[candidates[-1]] >= key[start]:
                candidates.pop()
            candidates.append(start)

        while candidates and load[end] - load[candidates[0]] > exact_capacity:
            candidates.popleft()

        if candidates:
            pred[end] = candidates[0]
            best[end] = key[pred[end]] + distance[end] + exact_to[end - 1]

    if best[n] is None:
        return None

    routes: list[tuple[int, int]] = []
    end = n
    while end:
        start = pred[end]
        routes.append((start, end))
        end = start
    routes.reverse()
    cost = float(best[n]) if float_distance else best[n]
    return cost, routes
