# CASE-038 CVRP polar petal generation and set partitioning

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-038.json](CASE-038.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-050](../../algorithms/ALG-050/ALG-050.md), [ALG-061](../../algorithms/ALG-061/ALG-061.md), [ALG-057](../../algorithms/ALG-057/ALG-057.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The petal-route candidate family and set partitioning relationship, checked with the authors' PDF. [Ryan, Hjorring and Glover, Extensions of the Petal Method for Vehicle Routeing (1993)](https://doi.org/10.1057/jors.1993.54)
- The authors' description of polar angle as the grouping order. [Gillett and Miller, A Heuristic Algorithm for the Vehicle-Dispatch Problem (1974)](https://pubsonline.informs.org/doi/10.1287/opre.22.2.340)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `ce3b9047d86147b7b324aea2691e5065e175a1ff51c89c41927a28b4b2a5b9f6`.
