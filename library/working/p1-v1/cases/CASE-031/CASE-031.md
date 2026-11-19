# CASE-031 CVRP tabu interroute relocate with record-triggered tail improvement

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-031.json](CASE-031.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md), [ALG-064](../../algorithms/ALG-064/ALG-064.md), [ALG-054](../../algorithms/ALG-054/ALG-054.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Tabu restrictions and aspiration in the author paper. [Fred Glover, Tabu Search—Part I (1989)](https://doi.org/10.1287/ijoc.1.3.190)
- The author-described customer reinsertion across routes within TABUROUTE. [Gendreau, Hertz and Laporte, A Tabu Search Heuristic for the Vehicle Routing Problem (1994)](https://pubsonline.informs.org/doi/10.1287/mnsc.40.10.1276)
- Interroute exchange reference for the 2-opt* neighborhood. [Potvin and Rousseau, An Exchange Heuristic for Routeing Problems with Time Windows (1995)](https://doi.org/10.1057/jors.1995.204)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `4f2043739bb0c8f11d9b6c5e592453688d9a9110e84965a2386d4dc1b2f6de2e`.
