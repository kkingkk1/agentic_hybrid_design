"""Partially mapped crossover for permutations."""


def pmx(first, second, left, right):
    """Copy first[left:right] and resolve conflicting second-parent values."""
    if len(first) != len(second) or set(first) != set(second) or len(set(first)) != len(first):
        raise ValueError("parents must permute the same unique values")
    if not 0 <= left <= right <= len(first):
        raise ValueError("invalid crossover interval")
    mapping = dict(zip(first[left:right], second[left:right]))
    child = list(second)
    child[left:right] = first[left:right]
    for index in (*range(left), *range(right, len(first))):
        value = child[index]
        while value in mapping:
            value = mapping[value]
        child[index] = value
    return child
