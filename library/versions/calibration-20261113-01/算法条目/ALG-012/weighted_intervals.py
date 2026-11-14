"""单资源加权区间调度的动态规划。"""

from bisect import bisect_right
from fractions import Fraction
from math import isfinite


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not isfinite(value)):
        raise ValueError("区间端点和权重须为有限数值")
    return Fraction(value)


def weighted_intervals(intervals):
    """输入 (开始, 结束, 权重)，返回最大权重及原列表下标。"""
    items = []
    for index, (start, end, weight) in enumerate(intervals):
        a, b, w = _number(start), _number(end), _number(weight)
        if a >= b:
            raise ValueError("区间开始时间必须早于结束时间")
        items.append((b, a, index, w))
    items.sort(key=lambda item: (item[0], item[1], item[2]))
    ends = [item[0] for item in items]
    dp = [Fraction(0)]
    previous = []
    for i, (end, start, index, weight) in enumerate(items):
        j = bisect_right(ends, start, 0, i)
        previous.append(j)
        dp.append(max(dp[-1], weight + dp[j]))
    selected = []
    i = len(items)
    while i:
        if items[i - 1][3] + dp[previous[i - 1]] > dp[i - 1]:
            selected.append(items[i - 1][2])
            i = previous[i - 1]
        else:
            i -= 1
    selected.reverse()
    return dp[-1], selected
