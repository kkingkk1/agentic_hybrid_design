"""检查 P0 实例映射与物理核资源边界。"""

import copy
import json
import os
import subprocess
import sys
import unittest

from scripts.p0_cpu_topology import PROJECT, read_windows_topology, select_mapping


@unittest.skipUnless(os.name == "nt", "P0 物理核合同仅适用于当前 Windows 主机")
class P0CpuTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = read_windows_topology()

    def test_assigns_distinct_physical_cores_and_reserves_four_p_cores(self):
        result = select_mapping(*self.topology)
        self.assertEqual([w["logical_processor"] for w in result["workers"]],
                         list(range(16, 28)) + [8, 10, 12, 14])
        self.assertEqual(result["reserved_p_cores"], [[0, 1], [2, 3], [4, 5], [6, 7]])
        self.assertEqual(len(result["instances"]), 15)
        self.assertEqual(len({item["instance_id"] for item in result["instances"]}), 15)
        cores, _, _, _ = self.topology
        selected = {w["logical_processor"] for w in result["workers"]}
        self.assertEqual(sum(bool(selected.intersection(core["logical"])) for core in cores), 16)

    def test_rejects_unavailable_or_changed_topology(self):
        cores, cpu_sets, process_mask, system_mask = self.topology
        with self.assertRaises(ValueError):
            select_mapping(cores, cpu_sets, process_mask & ~(1 << 16), system_mask)
        changed = copy.deepcopy(cores)
        changed[0]["efficiency"] = 9
        with self.assertRaises(ValueError):
            select_mapping(changed, cpu_sets, process_mask, system_mask)
        allocated = copy.deepcopy(cpu_sets)
        allocated[(0, 16)]["flags"] |= 0x02
        with self.assertRaises(ValueError):
            select_mapping(cores, allocated, process_mask, system_mask)

    def test_cli_reports_mapping_as_json(self):
        result = subprocess.run(
            [sys.executable, "-B", str(PROJECT / "scripts" / "p0_cpu_topology.py")],
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(len(json.loads(result.stdout)["workers"]), 16)


if __name__ == "__main__":
    unittest.main()
