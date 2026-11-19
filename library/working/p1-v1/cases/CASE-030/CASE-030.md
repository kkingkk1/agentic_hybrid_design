# CASE-030 CVRP adaptive large-neighborhood search with independent operator weights

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-030.json](CASE-030.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-059](../../algorithms/ALG-059/ALG-059.md), [ALG-008](../../algorithms/ALG-008/ALG-008.md), [ALG-058](../../algorithms/ALG-058/ALG-058.md), [ALG-004](../../algorithms/ALG-004/ALG-004.md), [ALG-003](../../algorithms/ALG-003/ALG-003.md), [ALG-007](../../algorithms/ALG-007/ALG-007.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Algorithm 1 and sections 3.1–3.5 in the project's previously acquired published-version text. [Røpke and Pisinger, An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows (2006)](https://doi.org/10.1287/trsc.1050.0135)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `b599ec8852c950371b9a678b047944125e3de97e9e7461b72d594f2e416784ac`.
