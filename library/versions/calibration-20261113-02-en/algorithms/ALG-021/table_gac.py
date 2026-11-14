"""显式允许元组表约束的广义弧一致性过滤。"""


def table_gac(domains, allowed_tuples):
    """返回每个域有表支持的值；无支持元组返回 None。"""
    current = [set(values) for values in domains]
    compatible = []
    for row in allowed_tuples:
        if len(row) != len(current):
            raise ValueError("元组长度必须与变量数一致")
        if all(value in current[i] for i, value in enumerate(row)):
            compatible.append(tuple(row))
    if not compatible:
        return None
    return [{row[i] for row in compatible} for i in range(len(current))]
