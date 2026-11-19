# CASE-020 TSP multifragment construction with exact bounded-window reordering

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-020.json](CASE-020.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-037](../../algorithms/ALG-037/ALG-037.md), [ALG-061](../../algorithms/ALG-061/ALG-061.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Section 2.2.2 on sorted edges, degree limits and premature subtours. [Comparing Greedy Constructive Heuristic Subtour Elimination Methods for the Traveling Salesman Problem](https://arxiv.org/abs/1910.08625)
- The use_tsp_opt exact subchain operator documentation inspected on 2026-11-18. [Google OR-Tools, routing_parameters.proto](https://github.com/google/or-tools/blob/stable/ortools/constraint_solver/routing_parameters.proto)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `f26f7854b872d344131d4abaa5633c30d7b29db06d80e8bc4dc3e30b95530ee8`.
