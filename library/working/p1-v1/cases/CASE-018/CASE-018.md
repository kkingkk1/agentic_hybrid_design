# CASE-018 TSP GRASP with elite path relinking

The entry records a complete Python 3.13 callable reference for TSP. Restore the files named in the manifest beside each other and call the `solve` function in `solver.py`. The file uses the standard library and the declared shared components. [CASE-018.json](CASE-018.json) · [solver.py](solver.py)

The shared source files are assembled from [ALG-048](../../algorithms/ALG-048/ALG-048.md), [ALG-063](../../algorithms/ALG-063/ALG-063.md), [ALG-005](../../algorithms/ALG-005/ALG-005.md). Their normalized hashes and the case file's hash are pinned in the manifest.

## Source and scope

The project implementation uses the connection or mechanism supported by the references below. The case entry describes the actual transfer, stopping conditions and limits of the adaptation.

- Randomized greedy construction via a restricted candidate list and subsequent local improvement. [Feo and Resende, Greedy Randomized Adaptive Search Procedures (1995)](http://www2.imm.dtu.dk/courses/02719/grasp/original_grasp.pdf)
- The elite-guided search path between source and target solutions. [Resende and Ribeiro, GRASP with Path-Relinking: Recent Advances and Applications](https://mauricio.resende.info/doc/sgrasppr.pdf)

## Validation

On 2026-11-18 the declared modules and solver were executed in isolation on six small fixtures using CPython 3.13.12. An independent check recomputed travel costs, verified exact coverage and confirmed that the supplied data were unchanged. The evidence concerns these small fixtures and the recorded interface.

The JSON SHA-256 is `b0d49647d4424bb9210c23da70eaaea1c9e2995ce2bf0b1c7d51ac9d218cff39`.
