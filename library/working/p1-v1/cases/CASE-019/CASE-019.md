# CASE-019 TSP general variable neighborhood search

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-019.json](CASE-019.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-035](../../algorithms/ALG-035/ALG-035.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md), [ALG-042](../../algorithms/ALG-042/ALG-042.md), [ALG-034](../../algorithms/ALG-034/ALG-034.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Shaking, descent and changing neighborhoods on success or failure. [Hansen and Mladenović, Variable Neighborhood Search: Principles and Applications (2001)](https://doi.org/10.1016/S0377-2217(00)00100-4)
- The Or-opt code in the project's calibration copy, including consecutive-block relocation. [Shunji Umetani, tsp_ils.py at commit 1122bd112e6cd62f5733c2a722b96b78af015c07](https://github.com/shunji-umetani/tsp-solver/blob/1122bd112e6cd62f5733c2a722b96b78af015c07/tsp_ils.py#L303)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `cb3d054bd5b3c95447c63662a9a932c01b6e2d47060d5bf66da59cb961a96010`.
