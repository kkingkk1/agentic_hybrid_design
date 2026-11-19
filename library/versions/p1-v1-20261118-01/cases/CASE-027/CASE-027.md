# CASE-027 CVRP Clarke–Wright savings followed by feasible relocate descent

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-027.json](CASE-027.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-049](../../algorithms/ALG-049/ALG-049.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The central-depot route-construction paper record. [Clarke and Wright, Scheduling of Vehicles from a Central Depot to a Number of Delivery Points (1964)](https://pubsonline.informs.org/doi/10.1287/opre.12.4.568)
- Section 6.4.12 and algorithm 6.7 on computing savings and joining compatible route ends. [Larson and Odoni, Urban Operations Research](https://web.mit.edu/urban_or_book/www/book/chapter6/6.4.12.html)
- The checked route neighborhoods in the inherited author-version source. [Thibaut Vidal, HGS-CVRP source at commit 35b32d8e9552074f52444d51ea1fe8aec9055467](https://github.com/vidalt/HGS-CVRP/blob/35b32d8e9552074f52444d51ea1fe8aec9055467/Program/LocalSearch.cpp)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `0be1e1b14c7810f824017324b69dfd087ffde4f81cff64259fea85dbda6a4703`.
