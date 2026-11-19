# CASE-033 CVRP partial reoptimization of geographically related route pairs

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-033.json](CASE-033.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md), [ALG-054](../../algorithms/ALG-054/ALG-054.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Fixing decisions outside a selected routing subproblem. [A POPMUSIC Matheuristic for the Capacitated Vehicle Routing Problem (2021)](https://doi.org/10.1016/j.cor.2021.105475)
- The route-column formulation, pricing feedback and partial reoptimization illustrations. [Ruslan Sadykov, Practical Relevance of the State-of-the-Art Exact VRP Solvers (DIMACS 2023)](https://www.math.u-bordeaux.fr/~rsadykov/slides/Sadykov_DIMACS23slides.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `c9e91f2a1dfc24d266d49b6099cadeb8690f8ecb73d81e8dae4b16859a3831ee`.
