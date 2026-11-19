# CASE-022 TSP annealed reversal moves followed by Or-opt

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-022.json](CASE-022.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-036](../../algorithms/ALG-036/ALG-036.md), [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-007](../../algorithms/ALG-007/ALG-007.md), [ALG-042](../../algorithms/ALG-042/ALG-042.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Algorithm 1 and sections 3.1–3.5 in the project's previously acquired published-version text. [Røpke and Pisinger, An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows (2006)](https://doi.org/10.1287/trsc.1050.0135)
- The Or-opt code in the project's calibration copy, including consecutive-block relocation. [Shunji Umetani, tsp_ils.py at commit 1122bd112e6cd62f5733c2a722b96b78af015c07](https://github.com/shunji-umetani/tsp-solver/blob/1122bd112e6cd62f5733c2a722b96b78af015c07/tsp_ils.py#L303)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `1cec6a514efd7f8d375a95cc7a5a15192281dfe2a1d22380dd14fd6380ae9bc3`.
