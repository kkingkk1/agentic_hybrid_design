# CASE-035 CVRP selective route exchange with explicit offspring repair

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-035.json](CASE-035.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-051](../../algorithms/ALG-051/ALG-051.md), [ALG-058](../../algorithms/ALG-058/ALG-058.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The documented selective route exchange followed by offspring repair. [PyVRP, selective_route_exchange.py at revision bd7194a](https://github.com/PyVRP/PyVRP/blob/bd7194a/pyvrp/crossover/selective_route_exchange.py)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `808349a4e17baae431fe1396831d1c9b11d40bd3f1faf3447f852e698e88caa7`.
