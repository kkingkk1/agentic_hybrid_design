"""检查16身份并发验证不会误接受重复身份或绑定。"""

import base64
import json
import os
import unittest
from unittest.mock import patch

from scripts import p0_slot_verify as verify


@unittest.skipUnless(os.name == "nt", "测试身份仅适用于 Windows")
class P0SlotVerifyTests(unittest.TestCase):
    def test_parallel_check_rejects_duplicate_identity_and_missing_overlap(self):
        results = []
        for index in range(16):
            pid, logical = 1000 + index, 16 + index
            output = json.dumps({"pid": pid, "affinity": 1 << logical}).encode()
            results.append({"profile_name": f"profile-{index}", "pid": pid, "logical_processor": logical,
                            "reason": "exited", "exit_code": 0,
                            "stdout_b64": base64.b64encode(output).decode(),
                            "resumed_monotonic": 10 + index / 100, "finished_monotonic": 20})
        self.assertTrue(verify._parallel_passed(results))
        changed = [dict(item) for item in results]
        changed[-1]["profile_name"] = changed[0]["profile_name"]
        self.assertFalse(verify._parallel_passed(changed))
        changed = [dict(item) for item in results]
        changed[-1]["resumed_monotonic"] = 21
        self.assertFalse(verify._parallel_passed(changed))
        changed = [dict(item) for item in results]
        changed[-1]["logical_processor"] = changed[0]["logical_processor"]
        self.assertFalse(verify._parallel_passed(changed))

    def test_changed_plan_stops_before_reading_profiles(self):
        with patch.object(verify.setup, "build_plan", return_value={"expected": True}), \
                patch.object(verify.identity, "_recorded_profile") as read_profile:
            with self.assertRaises(ValueError):
                verify._profiles({"expected": False})
            read_profile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
