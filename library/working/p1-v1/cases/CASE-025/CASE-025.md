# CASE-025 CVRP rotated sweep and exact ordering of small route clusters

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-025.json](CASE-025.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-050](../../algorithms/ALG-050/ALG-050.md), [ALG-051](../../algorithms/ALG-051/ALG-051.md), [ALG-061](../../algorithms/ALG-061/ALG-061.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The authors' description of polar angle as the grouping order. [Gillett and Miller, A Heuristic Algorithm for the Vehicle-Dispatch Problem (1974)](https://pubsonline.informs.org/doi/10.1287/opre.22.2.340)
- The use_tsp_opt exact subchain operator documentation inspected on 2026-11-18. [Google OR-Tools, routing_parameters.proto](https://github.com/google/or-tools/blob/stable/ortools/constraint_solver/routing_parameters.proto)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `e52890729301daceff3fdf59dad26d27dd5f3e30663b79be4d7844e3b340c5bf`.
