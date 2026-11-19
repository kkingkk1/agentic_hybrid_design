"""Stable permutation decoding for finite random keys."""


def random_key_tour(keys):
    """Order vertex indices by ascending (key, index)."""
    return sorted(range(len(keys)), key=lambda index: (keys[index], index))
