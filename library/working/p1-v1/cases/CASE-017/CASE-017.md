# CASE-017 TSP permutation memetic search with edge and mapping crossover

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-017.json](CASE-017.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-036](../../algorithms/ALG-036/ALG-036.md), [ALG-046](../../algorithms/ALG-046/ALG-046.md), [ALG-045](../../algorithms/ALG-045/ALG-045.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md), [ALG-041](../../algorithms/ALG-041/ALG-041.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The genetic local search loop for TSP. [Merz and Freisleben, Genetic Local Search for the TSP: New Results (1997)](https://redmine.iam.upr.si/attachments/download/243/Genetic_Local_Search_for_the_TSP.pdf)
- The genetic edge recombination paper record. [Whitley, Starkweather and Fuquay, Scheduling Problems and Traveling Salesmen (1989)](https://dl.acm.org/citation.cfm?id=93174)
- The cxPartialyMatched entry and mappings in the inspected documentation on 2026-11-18. [DEAP, crossover module documentation](https://deap.readthedocs.io/en/latest/_modules/deap/tools/crossover.html)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `191fa961d3cdef6ae414907183e12e779271da56adf4904a0111d02e42f54196`.
