# CASE-003: Iterated local search for TSP

**Case file:** [CASE-003.json](CASE-003.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** The program uses customer permutations and rounded distances for two-dimensional symmetric Euclidean TSP. Its entry constructs an initial tour by nearest neighbor, copies the current best tour for double-bridge perturbation, applies 2-opt, Or-opt, and 3-opt local searches in order, and updates the best when the candidate improves it. The loop stops at a time limit.

**Limits and transfer:** Perturbation reorders `tour` without synchronizing `pos`, but local search uses `pos` to find predecessors, successors, and move positions. An inconsistent position index was reproduced with a 10-node input, so move evaluations and resulting outputs cannot be trusted directly. Synchronize the indices and independently check the permutation and tour length before reuse. Perturbation requires enough nodes. The original program also unconditionally imports networkx and matplotlib even when plotting is disabled.

**Validation scope:** On 2026-11-12, missing networkx plotting imports were replaced with in-memory stubs, and nearest-neighbor construction, local search, and a short iteration were run on a synthetic 10-node input. Permutations, tour lengths, and performance no worse than the initial local solution were checked. A similar input reproduced the position-index issue. This does not establish that the original environment has all dependencies or that the implementation is generally correct.

**Source and conditions:** The code comes from [shunji-umetani/tsp-solver at a fixed commit](https://github.com/shunji-umetani/tsp-solver/tree/1122bd112e6cd62f5733c2a722b96b78af015c07), commit `1122bd112e6cd62f5733c2a722b96b78af015c07`. The entry point is [tsp_ils.py](tsp_ils.py). This case retains 2 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Relation to the algorithm library:** Its 2-opt has a related role to [ALG-005](../../algorithms/ALG-005/ALG-005.json), but source and interface differ and no implementation is shared.

**JSON version:** The current UTF-8 JSON SHA-256 is `6d1b951853c25eb21ab29e085d9a8948f1dc64817d08e28d33d960fa45102c09`; update this record if the JSON changes.
