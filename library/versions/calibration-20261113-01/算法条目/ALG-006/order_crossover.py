"""循环区间的顺序交叉，返回一个排列子代。"""

from typing import Hashable, Sequence, TypeVar


Gene = TypeVar("Gene", bound=Hashable)


def order_crossover(
    parent1: Sequence[Gene], parent2: Sequence[Gene], start: int, end: int
) -> list[Gene]:
    """保留第一父代从 start 至 end 的循环闭区间，余位按第二父代填充。

    两个父代必须是同一组不重复、可哈希元素的非空排列。区间可跨越末尾，
    当 end 是 start 的循环前驱时保留完整排列。切点由调用方选择。
    本函数只重组排列，不划分车辆路线或检查其他约束。
    """
    first, second = list(parent1), list(parent2)
    n = len(first)
    if n == 0 or len(second) != n:
        raise ValueError("需要两个长度相等的非空排列")
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n for i in (start, end)):
        raise ValueError("切点必须是有效的整数下标")
    try:
        first_set, second_set = set(first), set(second)
    except TypeError as exc:
        raise ValueError("排列元素必须可哈希") from exc
    if len(first_set) != n or len(second_set) != n or first_set != second_set:
        raise ValueError("父代必须是相同元素的不重复排列")

    empty = object()
    child = [empty] * n
    copied = set()
    i = start
    while True:
        child[i] = first[i]
        copied.add(first[i])
        if i == end:
            break
        i = (i + 1) % n

    target = (end + 1) % n
    for offset in range(n):
        gene = second[(end + 1 + offset) % n]
        if gene not in copied:
            child[target] = gene
            target = (target + 1) % n
    return child
