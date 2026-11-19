# CASE-024 CVRP giant-tour construction, capacity Split and interroute relocation

The entry records a complete Python 3.13 callable reference for CVRP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-024.json](CASE-024.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-051](../../algorithms/ALG-051/ALG-051.md), [ALG-053](../../algorithms/ALG-053/ALG-053.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The giant-tour construction followed by consecutive route partitioning. [J. E. Beasley, Route First–Cluster Second Methods for Vehicle Routing (1983)](https://people.brunel.ac.uk/%7Emastjjb/jeb/papers/omega_83.pdf)
- The checked route neighborhoods in the inherited author-version source. [Thibaut Vidal, HGS-CVRP source at commit 35b32d8e9552074f52444d51ea1fe8aec9055467](https://github.com/vidalt/HGS-CVRP/blob/35b32d8e9552074f52444d51ea1fe8aec9055467/Program/LocalSearch.cpp)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage, checked route capacity and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `a0fa31d35c8beb8df8dbcf56bacbaeafee33fab51f5865891fd9647931e3b8c2`.
