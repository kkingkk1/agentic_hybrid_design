# CASE-009: Population crossover and local search for vehicle routing

**Case file:** [CASE-009.json](CASE-009.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** The program reads a vehicle-routing instance, initializes a population of solutions, and locally searches the initial population. It repeatedly selects parents, produces and improves offspring, replaces population members, and updates the best solution. Crossover alternately selects whole routes from each parent that do not overlap already selected customers, then completes the offspring with the configured insertion policy. With crossover disabled it copies the first parent. Local operators, crossover, and stopping are configured on the command line; input structure includes capacity, pickup-delivery demands, and time-window fields.

**Limits and transfer:** This case records the actual framework of a configurable program and does not equate arbitrary configurations with a specific experiment in a paper. Different operators and instance formats can change behavior. Validate the chosen configuration, node coverage, capacity, and time-window semantics individually when transferring.

**Validation scope:** On 2026-11-12, `g++ -std=c++17 -fsyntax-only` successfully checked every C++ implementation file. No instance was linked or run and no performance comparison was made.

**Source and conditions:** The code comes from [senshineL/VRPenstein at a fixed commit](https://github.com/senshineL/VRPenstein/tree/c912c57aa387d31c20c036f11d0bca3c69ce93da), commit `c912c57aa387d31c20c036f11d0bca3c69ce93da`. The entry point is [SRC/VRPenstein.cpp](SRC/VRPenstein.cpp). This case retains 18 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Additional license:** In addition to the repository's MIT license, the header of `SRC/argparse.h` contains Hilton Bristow's BSD 3-Clause license; retain both notices.

**Relation to the algorithm library:** The case source is that repository's version; its crossover and local operators do not reference the algorithm library's independent implementations.

**JSON version:** The current UTF-8 JSON SHA-256 is `75e9a3a3d17e97fa3dd04d481865a5d9a8c4fce59879f1dae49f22c988906fc6`; update this record if the JSON changes.
