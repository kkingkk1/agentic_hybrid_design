"""按移除收益排序并随机化选择的 Worst Removal 组件。"""

from fractions import Fraction
from math import isfinite
from typing import Callable, Hashable, Mapping, Sequence, TypeVar


Node = TypeVar("Node", bound=Hashable)
Request = TypeVar("Request", bound=Hashable)


def _draw(rng) -> float:
    value = rng.random()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1:
        raise ValueError("随机数必须位于 [0, 1)")
    return value


def _biased_index(rng, power: int | float, size: int) -> int:
    draw = _draw(rng)
    try:
        scaled = draw ** power
    except OverflowError:
        # 巨大的正整数指数不能转成浮点数；有限浮点 draw < 1 时秩为 0。
        scaled = 0.0
    return int(scaled * size)


def _cost(value: int | float) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not isfinite(value)):
        raise ValueError("目标函数必须返回有限数值")
    return Fraction(value)


def worst_removal(
    routes: Sequence[Sequence[Node]],
    node_request: Mapping[Node, Request],
    count: int,
    power: int | float,
    objective: Callable[[tuple[tuple[Node, ...], ...]], int | float],
    rng,
) -> tuple[list[list[Node]], list[Request]]:
    """逐次重算移除收益，返回新路线和移除请求，不修改输入。

    routes 不含仓库；node_request 恰好覆盖访问节点，且一个请求的
    节点须在同一路线。objective 接收路线快照，计算不含请求银行罚项
    的目标值。请求被完全移除而不是移动到目标函数中的请求银行。
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("移除数量必须为非负整数")
    if isinstance(power, bool) or not isinstance(power, (int, float)) or power < 1 or (isinstance(power, float) and not isfinite(power)):
        raise ValueError("偏向参数必须是有限数且不小于 1")
    working = [list(route) for route in routes]
    nodes = [node for route in working for node in route]
    try:
        if len(set(nodes)) != len(nodes) or set(nodes) != set(node_request):
            raise ValueError("节点不得重复，映射必须恰好覆盖所有访问节点")
        request_route = {}
        for route_index, route in enumerate(working):
            for node in route:
                request = node_request[node]
                if request in request_route and request_route[request] != route_index:
                    raise ValueError("同一请求的节点必须属于同一路线")
                request_route[request] = route_index
    except TypeError as exc:
        raise ValueError("节点和请求必须可哈希") from exc
    pending = list(request_route)
    if count > len(pending):
        raise ValueError("移除数量超过已安排的请求数")

    removed = []
    for _ in range(count):
        current = _cost(objective(tuple(tuple(route) for route in working)))
        choices = []
        for request in pending:
            candidate = [[node for node in route if node_request[node] != request] for route in working]
            after = _cost(objective(tuple(tuple(route) for route in candidate)))
            choices.append((current - after, request, candidate))
        choices.sort(key=lambda choice: choice[0], reverse=True)
        _, selected, working = choices[_biased_index(rng, power, len(choices))]
        pending.remove(selected)
        removed.append(selected)
    return working, removed
