# CASE-039 Exact small ATSP with assignment-relaxation subtour branching

The entry records a complete Python 3.13 callable reference for ATSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-039.json](CASE-039.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-028](../../algorithms/ALG-028/ALG-028.md), [ALG-044](../../algorithms/ALG-044/ALG-044.md), [ALG-034](../../algorithms/ALG-034/ALG-034.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Assignment-relaxation bounds and subtour-elimination branching. [Carpaneto, Dell’Amico and Toth, Exact Solution of Large-Scale, Asymmetric Traveling Salesman Problems (1995)](https://doi.org/10.1145/212066.212081)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. All six fixture objectives agreed with exhaustive tour enumeration. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `83d9751c84960c898233d2f298f69999831291888bf4ffd83ed34e411679d933`.
