# CASE-021 TSP guided local search with edge-feature penalties

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-021.json](CASE-021.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-035](../../algorithms/ALG-035/ALG-035.md), [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Feature penalties steering local search through an augmented objective. [Voudouris and Tsang, Guided Local Search and Its Application to the Traveling Salesman Problem](https://www.dcs.gla.ac.uk/~pat/ads2/java/TxSxP/papers/gls.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `e1fc8e38c94587faa795079c508e91d2cd6f175e694645281a467e5610a3b893`.
