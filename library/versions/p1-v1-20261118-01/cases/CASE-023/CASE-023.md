# CASE-023 Exact small symmetric TSP with a 1-tree certificate and subset fallback

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-023.json](CASE-023.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md), [ALG-062](../../algorithms/ALG-062/ALG-062.md), [ALG-010](../../algorithms/ALG-010/ALG-010.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The minimum 1-tree bound under vertex-weight transformations. [Held and Karp, The Traveling-Salesman Problem and Minimum Spanning Trees (1970)](https://pubsonline.informs.org/doi/10.1287/opre.18.6.1138)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. All six fixture objectives agreed with exhaustive tour enumeration. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `7e9fa56baffd31450e36e03b5660de98b04a83daa17f2297e36b19c2d70faec9`.
