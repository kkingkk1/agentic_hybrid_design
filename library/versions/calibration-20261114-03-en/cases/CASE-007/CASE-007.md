# CASE-007: Fleet reduction and large-neighborhood search for VRPTW

**Case file:** [CASE-007.json](CASE-007.json) uses the four-field template; its code is assembled from a file manifest.

**Problem and flow:** The input is a Solomon-format vehicle-routing instance with time windows; the entry reads a fixed 100 customers. After greedy construction, it reduces the fleet by removing and reinserting customers and, when necessary, calls ejection search for unserved requests. It then chooses destroy and repair operations, compares candidates with the best solution, and continues using the implementation's acceptance and removal-expansion rules. In the main phase the repair selector uses random-order insertion for random values 0–9 and Regret-2 for the remaining values; nesting in the code makes the other selection branches unreachable.

**Limits and transfer:** Fleet reduction counts to 200000 and main search to 500000, but an empty removal decrements the count and retries, so actual attempts are not bounded by that counter and may fail to stop in an extreme case. The entry directly reads an instance path from the command line; no instance is included. When a candidate is rejected early as infeasible or having too many routes, deviation variable `dev` may be unassigned or retain an old value yet is used for subsequent stagnation checks; on its first occurrence it may read an uninitialized variable. The code uses GCC-style headers. Check time windows, capacity, request coverage, and stopping budget when transferring it.

**Validation scope:** On 2026-11-12, `g++ -std=c++17 -fsyntax-only` successfully checked all C++ implementation files. No instance was linked or run, and constraint correctness and performance were not validated.

**Source and conditions:** The code comes from [ruishibasaki/vrptw_lns at a fixed commit](https://github.com/ruishibasaki/vrptw_lns/tree/b2b07e0ee3eb3ccb9951c19fd61018f8e60cef45), commit `b2b07e0ee3eb3ccb9951c19fd61018f8e60cef45`. The entry point is [main/main.cpp](main/main.cpp). This case retains 20 source files, including the original LICENSE, with no source changes. The repository is MIT-licensed; retain original copyright and license notices. The JSON manifest locks each file's LF-normalized SHA-256; each was also checked against its upstream Git blob hash at initial ingestion. The dependency list records the source program's requirements and does not imply that this project has installed them.

**Relation to the algorithm library:** Destroy and repair neighborhoods are independent implementations from that repository; similar names in other entries do not establish code sharing or identical behavior.

**JSON version:** The current UTF-8 JSON SHA-256 is `49c02a59f21fffc214a8d3b59031804d2e0349601c54c78da5d29dc6322f767f`; update this record if the JSON changes.
