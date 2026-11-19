# CASE-037 Exact small CVRP by complete route generation and set partitioning

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-037.json](CASE-037.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-061](../../algorithms/ALG-061/ALG-061.md), [ALG-057](../../algorithms/ALG-057/ALG-057.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The route-column formulation, pricing feedback and partial reoptimization illustrations. [Ruslan Sadykov, Practical Relevance of the State-of-the-Art Exact VRP Solvers (DIMACS 2023)](https://www.math.u-bordeaux.fr/~rsadykov/slides/Sadykov_DIMACS23slides.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. Four small fixture objectives agreed with enumeration of complete customer orders and every feasible cut pattern. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `e19293f4e259279be4960439d95c40a02c0f29ea6a3c5fff2e81d67792e40bb0`.
