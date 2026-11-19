# CASE-014 TSP doubled-tree shortcut followed by 2-opt descent

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-014.json](CASE-014.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-031](../../algorithms/ALG-031/ALG-031.md), [ALG-038](../../algorithms/ALG-038/ALG-038.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The doubled spanning-tree walk and metric shortcut construction. [Cornell CS 6820, Christofides’s 2-Approximation for Metric TSP (2022 course handout)](https://www.cs.cornell.edu/courses/cs6820/2022fa/Handouts/Christofides.pdf)
- The 3-Opt local optimization identified in the author's paper. [Jon Bentley, Fast Algorithms for Geometric Traveling Salesman Problems (1992)](https://pubsonline.informs.org/doi/10.1287/ijoc.4.4.387)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `b251d1febb18b3462b47b59c19991c8fb98b32831697c1a2d5755846309ae87b`.
