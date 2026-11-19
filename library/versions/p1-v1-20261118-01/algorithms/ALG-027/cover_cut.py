"""枚举分离 0/1 背包的违反 cover 不等式。"""

from fractions import Fraction
from itertools import combinations
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("输入须为有限数值")
    return Fraction(x)


def violated_cover(weights, capacity, point):
    """返回违反 cover 不等式的物品下标；无违反时返回 None。"""
    if len(weights) != len(point):
        raise ValueError("重量与解向量长度不一致")
    w, x, cap = list(map(_number, weights)), list(map(_number, point)), _number(capacity)
    if cap < 0 or any(a < 0 for a in w) or any(not 0 <= a <= 1 for a in x):
        raise ValueError("容量和重量须非负，点的各分量须在 [0,1]")
    for size in range(1, len(w) + 1):
        for subset in combinations(range(len(w)), size):
            if sum(w[i] for i in subset) > cap and sum(x[i] for i in subset) > size - 1:
                return subset
    return None
