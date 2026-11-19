# CASE-011 TSP iterated local search with double-bridge perturbation

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-011.json](CASE-011.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-034](../../algorithms/ALG-034/ALG-034.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md), [ALG-043](../../algorithms/ALG-043/ALG-043.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- The ILS control flow and the four-cut double-bridge move in figure 4. [Lourenço, Martin and Stützle, Iterated Local Search (author manuscript)](https://econ-papers.upf.edu/papers/513.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `18bc5d92acdd4d346d6720d34aeefca249aec2f433f65e4826ba6354476d6473`.
