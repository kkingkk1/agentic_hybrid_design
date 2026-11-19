# CASE-013 Metric TSP Christofides construction

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-013.json](CASE-013.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-031](../../algorithms/ALG-031/ALG-031.md), [ALG-040](../../algorithms/ALG-040/ALG-040.md), [ALG-039](../../algorithms/ALG-039/ALG-039.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The construction with odd-degree matching, an Eulerian multigraph and shortcutting. [Nicos Christofides, Worst-Case Analysis of a New Heuristic for the Travelling Salesman Problem (1976 report reprint)](https://doi.org/10.1007/s43069-021-00101-z)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `1b0fdcd6709a09def1addf7b9eebfc75e84f329fc8545db089959086083a85d3`.
