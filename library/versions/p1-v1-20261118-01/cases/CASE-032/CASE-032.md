# CASE-032 CVRP fleet reduction by route elimination and subsequent distance refinement

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-032.json](CASE-032.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-056](../../algorithms/ALG-056/ALG-056.md), [ALG-058](../../algorithms/ALG-058/ALG-058.md), [ALG-054](../../algorithms/ALG-054/ALG-054.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Route elimination as a first stage and travel distance as a secondary objective. [Nagata and Bräysy, A Powerful Route Minimization Heuristic for the Vehicle Routing Problem with Time Windows (2009)](https://www.sintef.no/globalassets/project/vip08/abstract_nagata.pdf)
- Interroute exchange reference for the 2-opt* neighborhood. [Potvin and Rousseau, An Exchange Heuristic for Routeing Problems with Time Windows (1995)](https://doi.org/10.1057/jors.1995.204)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `12cff1e105b6146216cb9bcceaf9d888d0697c9d1ce8cd3baf776bdfc69493c1`.
