# CASE-008: Variable-neighborhood search for CVRP

**Case file:** [CASE-008.json](CASE-008.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** Candidates are customer visit orders, from which CVRP evaluation builds routes under constraints. The example starts with a nearest-neighbor order and compares several methods. In VNS, each iteration randomly perturbs the order and then runs swap or insertion local search. A strict improvement updates the best and returns to the first neighborhood; otherwise the next neighborhood is tried. A timer may stop early.

**Limits and transfer:** When local search does not improve, the code retains the perturbed `current_solution` but leaves `current_solution_value` at its prior value. The next iteration therefore does not follow standard VNS restoration of the prior accepted solution. The example input file is not included. `main.py` imports `solver.py` before creating its log directory, so expected paths must be prepared beforehand. The evaluator checks only whether positions in the input order have been processed, not whether customers are duplicated or the complete customer set is covered. An input with one repeated and one missing customer was reproduced with finite cost. Independently check coverage, route decoding, and capacity when transferring.

**Validation scope:** On 2026-11-12, the VNS, evaluator, and main program source were inspected. CVRP VNS was run on a synthetic 5-customer instance with independent checks of customer coverage, capacity, and route cost; log-file and plot-directory creation were replaced by in-memory stubs for the test. An input with a repeated and missing customer also reproduced the evaluator's finite-cost issue. The original main program and real data were not run; original repository dependencies remain in `requirements.txt`.

**Source and conditions:** The code comes from [fdoborrego/vrp_optimization at a fixed commit](https://github.com/fdoborrego/vrp_optimization/tree/917607f8ff31031c4cfd74f1b13b38e03be6095a), commit `917607f8ff31031c4cfd74f1b13b38e03be6095a`. The entry point is [src/heuristics.py](src/heuristics.py). This case retains 8 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Relation to the algorithm library:** The case's neighborhoods and solver are independent implementations and share no files with the algorithm-library reference implementations.

**JSON version:** The current UTF-8 JSON SHA-256 is `a34f7181251b3f87fdef1f709e9afea99afcb3d4faa680edd430513e8f876961`; update this record if the JSON changes.
