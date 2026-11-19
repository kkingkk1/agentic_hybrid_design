# CASE-026 CVRP seeded generalized assignment followed by route optimization

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-026.json](CASE-026.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-052](../../algorithms/ALG-052/ALG-052.md), [ALG-061](../../algorithms/ALG-061/ALG-061.md), [ALG-049](../../algorithms/ALG-049/ALG-049.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The vehicle assignment stage followed by routing the assigned customers. [Fisher and Jaikumar, A Generalized Assignment Heuristic for Vehicle Routing (1981)](https://doi.org/10.1002/net.3230110205)
- The central-depot route-construction paper record. [Clarke and Wright, Scheduling of Vehicles from a Central Depot to a Number of Delivery Points (1964)](https://pubsonline.informs.org/doi/10.1287/opre.12.4.568)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `d0692708cdc288de81595c03c824f46d0a82e4c2e9a6a958c8799278e0d5cf3a`.
