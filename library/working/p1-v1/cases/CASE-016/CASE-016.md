# CASE-016 TSP biased random-key evolution with a local decoder

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-016.json](CASE-016.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-060](../../algorithms/ALG-060/ALG-060.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The basic BRKGA decoder, elite-biased mating and mutants described by the method's authors and coauthors. [Biased Random-Key Genetic Algorithms: A Review (author manuscript)](https://arxiv.org/abs/2312.00961)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `e5056f4eab542967e4c566781be462a61db7eda112ddbfd617ed90a60b9168d4`.
