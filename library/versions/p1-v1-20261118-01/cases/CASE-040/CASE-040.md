# CASE-040 CVRP LP-guided route pricing and restricted integer recombination

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-040.json](CASE-040.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-026](../../algorithms/ALG-026/ALG-026.md), [ALG-061](../../algorithms/ALG-061/ALG-061.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md), [ALG-057](../../algorithms/ALG-057/ALG-057.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Route-based LP column generation and resource-constrained route pricing. [Desrochers, Desrosiers and Solomon, A New Optimization Algorithm for the Vehicle Routing Problem with Time Windows (1992)](https://doi.org/10.1287/opre.40.2.342)
- The route-column formulation, pricing feedback and partial reoptimization illustrations. [Ruslan Sadykov, Practical Relevance of the State-of-the-Art Exact VRP Solvers (DIMACS 2023)](https://www.math.u-bordeaux.fr/~rsadykov/slides/Sadykov_DIMACS23slides.pdf)
- The combination of a heuristic route pool and set partitioning. [Subramanian, Uchoa and Ochi, A Hybrid Algorithm for a Class of Vehicle Routing Problems (2013)](https://luizsatoru.github.io/conteudo/artigos/COR2013-ANAND.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The returned disjoint cover also cost no more than the singleton-only cover in each fixture. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `84b9846c7c07379bf4ad0e75c1619eb4bdfbb04eb51359854ff1d5078cd84655`.
