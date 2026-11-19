# CASE-015 ATSP assignment cycle cover and greedy patching

The entry records a complete Python 3.13 callable reference for ATSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-015.json](CASE-015.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-028](../../algorithms/ALG-028/ALG-028.md), [ALG-044](../../algorithms/ALG-044/ALG-044.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The assignment and patching reference record. [Richard M. Karp, A Patching Algorithm for the Nonsymmetric Traveling-Salesman Problem (1978 technical report M78/2)](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1978/28924.html)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `ebadd5d9edb698e57c7a113de8170da101c50d334b69a02c055cf9c50cf51a1d`.
