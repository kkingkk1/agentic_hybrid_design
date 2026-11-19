"""ALNS 的独立轮盘选择、结果计分和分段权重更新。"""

from fractions import Fraction
from math import isfinite
from typing import Sequence


def _number(value: int | float, *, nonnegative: bool = False) -> int | Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("输入必须是数值")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("输入必须是有限数值")
    if nonnegative and value < 0:
        raise ValueError("权重、得分和奖励必须非负")
    return Fraction(value) if isinstance(value, float) else value


def choose_operator(weights: Sequence[int | float], rng) -> int:
    """按权重抽取一个下标；rng.random() 须返回 [0, 1) 的数。"""
    exact = [_number(weight, nonnegative=True) for weight in weights]
    total = sum(exact)
    if not exact or total <= 0:
        raise ValueError("至少需要一个正权重")
    draw = _number(rng.random())
    if not 0 <= draw < 1:
        raise ValueError("随机数必须位于 [0, 1)")
    target = draw * total
    cumulative: int | Fraction = 0
    for index, weight in enumerate(exact):
        cumulative += weight
        if target < cumulative:
            return index
    raise RuntimeError("算子权重抽样失败")


def score_outcome(
    candidate: int | float,
    current: int | float,
    best: int | float,
    accepted: bool,
    previously_accepted: bool,
    rewards: Sequence[int | float],
) -> int | float:
    """按最小化目标计分；历史状态由调用方在本轮判断前提供。

    奖励依次对应新全局最好、此前未接受过且改善当前、此前未接受过且
    较差但被接受。重叠时按上述顺序取第一种；相等或其他情况得零分。
    """
    if len(rewards) != 3 or not isinstance(accepted, bool) or not isinstance(previously_accepted, bool):
        raise ValueError("需要三个奖励和布尔型状态")
    c, now, old_best = (_number(x) for x in (candidate, current, best))
    for reward in rewards:
        _number(reward, nonnegative=True)
    if c < old_best:
        return rewards[0]
    if not previously_accepted and c < now:
        return rewards[1]
    if not previously_accepted and c > now and accepted:
        return rewards[2]
    return 0


def update_weights(
    weights: Sequence[int | float],
    scores: Sequence[int | float],
    uses: Sequence[int],
    reaction: int | float,
) -> list[float]:
    """按段末累计分数和尝试次数更新；未调用算子的权重保持不变。"""
    if not weights or len(weights) != len(scores) or len(weights) != len(uses):
        raise ValueError("权重、得分和调用次数字段长度必须一致且非空")
    rate = _number(reaction)
    if not 0 <= rate <= 1:
        raise ValueError("反应系数必须位于 [0, 1]")
    result = []
    for weight, score, count in zip(weights, scores, uses):
        w = _number(weight, nonnegative=True)
        s = _number(score, nonnegative=True)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("尝试次数必须是非负整数")
        if count == 0:
            if s != 0:
                raise ValueError("未调用算子不能有本段得分")
            result.append(float(w))
        else:
            result.append(float((1 - rate) * w + rate * Fraction(s, count)))
    return result
