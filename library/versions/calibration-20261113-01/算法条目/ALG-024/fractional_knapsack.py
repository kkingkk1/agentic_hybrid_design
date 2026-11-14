"""分数背包线性松弛的贪心最优解。"""

from fractions import Fraction
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("输入须为有限数值")
    return Fraction(x)


def fractional_knapsack(weights, values, capacity):
    """返回松弛目标值和各物品取用比例；重量须正、价值须非负。"""
    if len(weights) != len(values):
        raise ValueError("重量与价值长度不一致")
    w, v, room = list(map(_number, weights)), list(map(_number, values)), _number(capacity)
    if room < 0 or any(x <= 0 for x in w) or any(x < 0 for x in v):
        raise ValueError("容量、重量或价值超出允许范围")
    selected = [Fraction(0)] * len(w)
    for i in sorted(range(len(w)), key=lambda i: v[i] / w[i], reverse=True):
        take = min(Fraction(1), room / w[i])
        selected[i] = take
        room -= take * w[i]
    return sum((v[i] * selected[i] for i in range(len(w))), Fraction(0)), selected
