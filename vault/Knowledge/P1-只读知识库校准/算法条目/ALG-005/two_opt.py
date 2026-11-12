"""对称 TSP 的完整下降 2-Opt 参考实现。"""

from fractions import Fraction
from math import isfinite
from typing import Sequence


def two_opt(
    tour: Sequence[int], distances: Sequence[Sequence[int | float]]
) -> tuple[int | float, list[int]]:
    """反复执行最佳改善，返回回路长度和不重复起点的回路节点顺序。

    距离矩阵须有限、非负、对称，主对角线为零；tour 必须恰好访问每个
    矩阵节点一次。末尾到起点的边隐含在回路中。空矩阵对应空回路。
    浮点距离按其二进制值精确比较，最终长度转回 float，可能舍入或溢出。
    只处理对称距离，不处理时间窗、容量等附加约束。
    """
    n = len(distances)
    if len(tour) != n or any(len(row) != n for row in distances):
        raise ValueError("回路与距离矩阵的维度不一致")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in tour):
        raise ValueError("回路节点必须是整数索引")
    if set(tour) != set(range(n)):
        raise ValueError("回路必须恰好包含每个节点一次")

    has_float = False
    matrix: list[list[int | Fraction]] = []
    for row in distances:
        exact_row: list[int | Fraction] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("距离必须是数值")
            if value < 0 or (isinstance(value, float) and not isfinite(value)):
                raise ValueError("距离必须是有限非负数")
            has_float |= isinstance(value, float)
            exact_row.append(Fraction(value) if isinstance(value, float) else value)
        matrix.append(exact_row)
    for i in range(n):
        if matrix[i][i] != 0:
            raise ValueError("距离矩阵主对角线必须为零")
        for j in range(i):
            if matrix[i][j] != matrix[j][i]:
                raise ValueError("距离矩阵必须对称")

    result = list(tour)
    while n >= 4:
        best_delta: int | Fraction = 0
        best_move = None
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue  # 首尾两条边相邻，不构成合法 2-Opt 移动。
                a, b = result[i], result[(i + 1) % n]
                c, d = result[j], result[(j + 1) % n]
                delta = matrix[a][c] + matrix[b][d] - matrix[a][b] - matrix[c][d]
                if delta < best_delta:
                    best_delta = delta
                    best_move = (i, j)
        if best_move is None:
            break
        i, j = best_move
        result[i + 1:j + 1] = reversed(result[i + 1:j + 1])

    cost = sum(matrix[result[i]][result[(i + 1) % n]] for i in range(n))
    return (float(cost) if has_float else cost), result
