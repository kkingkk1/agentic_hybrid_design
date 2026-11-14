# CASE-005: Ant colony and alternating local search for TSP

**Case file:** [CASE-005.json](CASE-005.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** Initialize pheromone from the nearest-neighbor tour length. Multiple ants construct tours using pheromone and distance, locally updating pheromone on traversed edges. Apply 2.5-opt to the best ant of an even iteration and 2-opt to a random ant of an odd iteration. Update the global best only for a strictly shorter tour, then perform a global pheromone update on its edges. Stop on the instance's known target, the iteration limit, or an approximate time limit.

**Limits and transfer:** `best_global_length` starts at the nearest-neighbor length, but `best_global_path` starts as an all-zero array. If neither ants nor local search strictly improve the nearest-neighbor length, the route used for pheromone updates and printing may not be a valid tour corresponding to that length. `aco_solution` returns tour length, not the tour; the route is printed only when `print_path` is enabled. Static source inspection confirmed the initialization gap. Save the initial tour and independently check node coverage and printed length before use. The entry requires a valid instance path and a supported instance format.

**Validation scope:** On 2026-11-12, `g++ -std=c++11 -fsyntax-only` successfully checked the entry and included headers. The full algorithm was not linked or run and performance was not evaluated.

**Source and conditions:** The code comes from [MicheleCattaneo/ant_colony_opt_TSP at a fixed commit](https://github.com/MicheleCattaneo/ant_colony_opt_TSP/tree/617fa90e14b06c27ff12d5afb729d49afef7b519), commit `617fa90e14b06c27ff12d5afb729d49afef7b519`. The entry point is [aco.cpp](aco.cpp). This case retains 9 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Relation to the algorithm library:** The case's 2-opt and [ALG-005](../../algorithms/ALG-005/ALG-005.json) are independently implemented.

**JSON version:** The current UTF-8 JSON SHA-256 is `fefd5f4769b0974928d024d7ea53927fed22b092533b0dcf4847d84a4a5e75be`; update this record if the JSON changes.
