"""以重复匹配判定支持的 AllDifferent 域一致性过滤。"""


def all_different_gac(domains):
    """返回每个值有完整不同值匹配的域；不存在匹配则返回 None。"""
    current = [set(values) for values in domains]
    if any(not values for values in current):
        return None

    def supported(forced_index, forced_value):
        matched = {forced_value: forced_index}

        def augment(index, seen):
            for value in current[index]:
                if value in seen or value == forced_value:
                    continue
                seen.add(value)
                if value not in matched or augment(matched[value], seen):
                    matched[value] = index
                    return True
            return False

        return all(augment(i, set()) for i in range(len(current)) if i != forced_index)

    result = [{value for value in choices if supported(i, value)} for i, choices in enumerate(current)]
    return result if all(result) else None
