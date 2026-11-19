"""按给定相关性选择并移除请求的 Shaw 组件。"""

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


def shaw_removal(
    routes: Sequence[Sequence[Node]],
    node_request: Mapping[Node, Request],
    count: int,
    power: int | float,
    relatedness: Callable[[Request, Request], int | float],
    rng,
) -> tuple[list[list[Node]], list[Request]]:
    """返回移除后的路线和所移除请求，输入不变。

    routes 仅含访问节点，不含仓库。node_request 须恰好覆盖全部节点；
    同一请求的节点须在同一路线上。relatedness 越小表示越相关，须由
    调用方依据移除前的解提供稳定值。power >= 1 控制相关性选择偏向。
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
    if count == 0:
        return working, []

    removed = [pending.pop(int(_draw(rng) * len(pending)))]
    while len(removed) < count:
        reference = removed[int(_draw(rng) * len(removed))]

        def relation(request):
            value = relatedness(reference, request)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not isfinite(value)):
                raise ValueError("相关性必须是有限数值")
            return value

        pending.sort(key=relation)
        index = _biased_index(rng, power, len(pending))
        removed.append(pending.pop(index))

    removed_set = set(removed)
    return [[node for node in route if node_request[node] not in removed_set] for route in working], removed
