# CASE-004: TSP size-dependent branches and local improvement

**Case file:** [CASE-004.json](CASE-004.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** The program reads coordinates, builds a rounded Euclidean distance matrix, and tries greedy routes from multiple starts. Automatic mode chooses the subsequent flow by node count: simulated annealing for at most 50 nodes; remove crossing paths then apply 2-opt for 51–500 nodes; and apply 2-opt directly for larger instances. The command line can override the choice, and results are written to a specified file.

**Limits and transfer:** The simulated-annealing branch uses `range(int(time / 30 - 1))` to choose the number of runs. For nonnegative times below 60 seconds, the loop does not run and final tour and cost are `None`. The caller must supply input paths and dependencies; the returned closed tour repeats the start. The time parameter is not a strict interruption guarantee shared by all branches.

**Validation scope:** On 2026-11-12, greedy construction and 2-opt were called separately on a synthetic 5-node distance matrix in the installed Python environment. Closed-tour structure, node coverage, distance, and the improvement relationship were independently checked. The default simulated-annealing branch and complete command line were not run.

**Source and conditions:** The code comes from [LaurenceLungo/TSP-Solver at a fixed commit](https://github.com/LaurenceLungo/TSP-Solver/tree/54ab033c84373238d09665d7d3b0e80c850c6501), commit `54ab033c84373238d09665d7d3b0e80c850c6501`. The entry point is [solve_tsp.py](solve_tsp.py). This case retains 8 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Relation to the algorithm library:** The case's 2-opt and [ALG-005](../../algorithms/ALG-005/ALG-005.json) are different implementations; this case does not call that algorithm entry's code.

**JSON version:** The current UTF-8 JSON SHA-256 is `acd6cbeb7b10da61d69781191477b039709f3f913cae18a876cf9b5aeea1434f`; update this record if the JSON changes.
