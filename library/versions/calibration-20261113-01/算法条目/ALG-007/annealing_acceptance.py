"""最小化问题的模拟退火接受与几何降温。"""

from fractions import Fraction
from math import isfinite, log


def _finite(value: int | float) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("目标值、温度和降温率必须是数值")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("目标值、温度和降温率必须有限")
    return Fraction(value)


def annealing_accept(current: int | float, candidate: int | float, temperature: int | float, rng) -> bool:
    """无条件接受不变或改善；较差解按 exp(-(candidate-current)/T) 接受。

    T 必须为正。仅对较差解调用 rng.random()；该值必须位于 [0, 1)。
    使用对数比较避免指数下溢；对数仍按浮点精度计算。
    """
    now, new, temp = _finite(current), _finite(candidate), _finite(temperature)
    if temp <= 0:
        raise ValueError("温度必须为正")
    if new <= now:
        return True
    draw = rng.random()
    if isinstance(draw, bool) or not isinstance(draw, (int, float)) or not 0 <= draw < 1:
        raise ValueError("随机数必须位于 [0, 1)")
    if draw == 0:
        return True
    return Fraction.from_float(-log(draw)) * temp > new - now


def cool_temperature(temperature: int | float, rate: int | float) -> float:
    """返回 T * rate；降温率必须严格位于 (0, 1)。"""
    temp, factor = _finite(temperature), _finite(rate)
    if temp <= 0 or not 0 < factor < 1:
        raise ValueError("温度必须为正，降温率必须位于 (0, 1)")
    result = float(temp * factor)
    if result == 0:
        raise ValueError("降温结果下溢为零；调用方须选择停止或其他处理")
    return result
