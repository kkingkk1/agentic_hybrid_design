# CASE-034 CVRP variable-neighborhood descent over tail, chain and single-customer moves

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-034.json](CASE-034.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-051](../../algorithms/ALG-051/ALG-051.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md), [ALG-054](../../algorithms/ALG-054/ALG-054.md), [ALG-055](../../algorithms/ALG-055/ALG-055.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Shaking, descent and changing neighborhoods on success or failure. [Hansen and Mladenović, Variable Neighborhood Search: Principles and Applications (2001)](https://doi.org/10.1016/S0377-2217(00)00100-4)
- The authors' exchange of consecutive customer sequences across routes. [Taillard, Badeau, Gendreau, Guertin and Potvin, A Tabu Search Heuristic for the Vehicle Routing Problem with Soft Time Windows (1997)](https://pubsonline.informs.org/doi/10.1287/trsc.31.2.170)
- Interroute exchange reference for the 2-opt* neighborhood. [Potvin and Rousseau, An Exchange Heuristic for Routeing Problems with Time Windows (1995)](https://doi.org/10.1057/jors.1995.204)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `76018adbbdea2600af0e9675b0ce01f62286a7951a77f8f30a333e36c0c7f976`.
