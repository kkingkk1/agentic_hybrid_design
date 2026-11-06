"""只读检查测试身份准备清单与执行前门禁。"""

import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from scripts import p0_slot_setup as setup


@unittest.skipUnless(os.name == "nt", "测试身份仅适用于 Windows")
class P0SlotSetupTests(unittest.TestCase):
    def test_plan_has_only_sixteen_distinct_named_targets(self):
        plan = setup.build_plan()
        self.assertEqual(plan["profile_count"], 16)
        self.assertEqual([item["name"] for item in plan["targets"]], list(setup.NAMES))
        self.assertEqual(len({item["profile_dir"].casefold() for item in plan["targets"]}), 16)
        self.assertEqual(plan["total_runtime_files"], 16 * plan["runtime_files_per_profile"])
        self.assertEqual(plan["total_runtime_bytes"], 16 * plan["runtime_bytes_per_profile"])
        for item in plan["targets"]:
            self.assertEqual(Path(item["runtime_dir"]).parent, Path(item["profile_dir"]))

    def test_changed_plan_stops_before_source_or_profile_work(self):
        plan = setup.build_plan()
        altered = {**plan, "profile_count": 15}
        with patch.object(setup.runtime, "build_manifest") as check_source, \
                patch.object(setup.identity, "run_probe") as create:
            with self.assertRaises(ValueError):
                setup._preflight(altered)
            check_source.assert_not_called()
            create.assert_not_called()

    def test_stop_signal_never_opens_runtime_source_or_destination(self):
        stop = threading.Event()
        stop.set()
        profile = {"profile_folder": r"C:\Test\AC"}
        target = {"profile_dir": r"C:\Test\AC", "runtime_dir": r"C:\Test\AC\runtime"}
        manifest = {"files": [{"path": "python.exe", "bytes": 1, "sha256": "0" * 64}]}
        with patch.object(Path, "mkdir"), patch.object(Path, "open") as open_file, \
                patch.object(setup.runtime, "_safe_stat"):
            with self.assertRaises(OSError):
                setup._copy_runtime(profile, target, Path(r"C:\Source"), manifest, stop)
            open_file.assert_not_called()

    def test_existing_record_requires_the_same_approved_plan(self):
        valid = b'{"event":"source","plan_sha256":"expected"}\n'
        with patch.object(Path, "read_bytes", return_value=valid):
            setup._check_plan_provenance(Path("record.jsonl"), "expected")
            with self.assertRaises(ValueError):
                setup._check_plan_provenance(Path("record.jsonl"), "different")


if __name__ == "__main__":
    unittest.main()
