"""基于逐路线最优插入的 Regret-k 请求安排。"""

from fractions import Fraction
from math import isfinite
from typing import Callable, Hashable, Sequence, TypeVar


Node = TypeVar("Node")
Request = TypeVar("Request", bound=Hashable)


def regret_k_insert(
    routes: Sequence[Sequence[Node]],
    requests: Sequence[Request],
    k: int,
    best_insertion: Callable[[tuple[Node, ...], Request], tuple[int | float, Sequence[Node]] | None],
) -> tuple[list[list[Node]], list[Request]]:
    """返回更新后的路线和未安排请求，不修改输入。

    best_insertion(route, request) 须返回该请求在此路线的最小可行
    目标增量及相应新路线；不可行时返回 None。调用方负责取送配对、
    先取后送、容量、时间窗等可行性及目标计算。请求不得重复。
    本函数只使用传入的路线，不主动创建车辆或路线。
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k 必须为正整数")
    pending = list(requests)
    if len(set(pending)) != len(pending):
        raise ValueError("待插入请求不能重复")
    working = [list(route) for route in routes]

    while pending:
        best_rank = None
        selected = None
        for request_index, request in enumerate(pending):
            options = []
            for route_index, route in enumerate(working):
                answer = best_insertion(tuple(route), request)
                if answer is None:
                    continue
                delta, new_route = answer
                if isinstance(delta, bool) or not isinstance(delta, (int, float)):
                    raise ValueError("插入代价必须是数值")
                if isinstance(delta, float) and not isfinite(delta):
                    raise ValueError("插入代价必须是有限数值")
                exact_delta = Fraction(delta) if isinstance(delta, float) else delta
                options.append((exact_delta, route_index, list(new_route)))
            if not options:
                continue
            options.sort(key=lambda option: (option[0], option[1]))
            best_delta = options[0][0]
            if len(options) < k:
                rank = (0, len(options), best_delta, request_index)
            else:
                regret = sum(option[0] - best_delta for option in options[:k])
                rank = (1, -regret, best_delta, request_index)
            if best_rank is None or rank < best_rank:
                best_rank = rank
                selected = (request_index, options[0][1], options[0][2])

        if selected is None:
            break
        request_index, route_index, new_route = selected
        working[route_index] = new_route
        del pending[request_index]

    return working, pending
