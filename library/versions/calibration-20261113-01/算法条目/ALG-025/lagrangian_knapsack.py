"""0/1 背包容量约束的拉格朗日上界。"""

from fractions import Fraction
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("输入须为有限数值")
    return Fraction(x)


def lagrangian_knapsack(weights, values, capacity, multiplier):
    """返回固定非负乘子下的上界及松弛子问题选择的物品下标。"""
    if len(weights) != len(values):
        raise ValueError("重量与价值长度不一致")
    w, v = list(map(_number, weights)), list(map(_number, values))
    cap, lam = _number(capacity), _number(multiplier)
    if cap < 0 or lam < 0 or any(x < 0 for x in w) or any(x < 0 for x in v):
        raise ValueError("容量、乘子、重量和价值须非负")
    chosen = [i for i in range(len(w)) if v[i] - lam * w[i] > 0]
    bound = lam * cap + sum((v[i] - lam * w[i] for i in chosen), Fraction(0))
    return bound, chosen
