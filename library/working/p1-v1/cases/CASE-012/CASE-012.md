# CASE-012 TSP Ant System with local-search feedback

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-012.json](CASE-012.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-047](../../algorithms/ALG-047/ALG-047.md), [ALG-041](../../algorithms/ALG-041/ALG-041.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Ant tour construction and evaporation/deposit feedback. [Dorigo, Maniezzo and Colorni, Ant System: Optimization by a Colony of Cooperating Agents (1996)](https://faculty.washington.edu/paymana/swarm/dorigo96-itsmc.pdf)
- The TSP variant coupling ant-generated tours with local search. [Dorigo and Gambardella, Ant Colony System: A Cooperative Learning Approach to the Traveling Salesman Problem (1997)](https://faculty.washington.edu/paymana/swarm/dorigo97-itec.pdf)
- The 3-Opt local optimization identified in the author's paper. [Jon Bentley, Fast Algorithms for Geometric Traveling Salesman Problems (1992)](https://pubsonline.informs.org/doi/10.1287/ijoc.4.4.387)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `1812c3ee51e445770769737a87e9a0033d2e2ff373cae73da8fedaaacb5c77a4`.
