# CASE-036 CVRP record-to-record travel with mixed feasible neighborhoods

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-036.json](CASE-036.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md), [ALG-054](../../algorithms/ALG-054/ALG-054.md), [ALG-065](../../algorithms/ALG-065/ALG-065.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The record-to-record travel approach to vehicle routing. [Li, Golden and Wasil, Very Large-Scale Vehicle Routing: New Test Problems, Algorithms, and Results (2005)](https://doi.org/10.1016/j.cor.2003.10.002)
- The record-to-record acceptance criterion used in the authors' comparison. [Santini, Røpke and Hvattum, A Comparison of Acceptance Criteria for the Adaptive Large Neighbourhood Search Metaheuristic](https://santini.in/files/papers/santini-ropke-hvattum-2018.pdf)
- Interroute exchange reference for the 2-opt* neighborhood. [Potvin and Rousseau, An Exchange Heuristic for Routeing Problems with Time Windows (1995)](https://doi.org/10.1057/jors.1995.204)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `4ed0393915d0be2033306d378fed8cc0355df49f0c6e6337dc3ba51b97953bcd`.
