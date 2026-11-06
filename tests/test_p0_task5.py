"""P0冻结包与任务5验收门禁。"""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import p0_task5 as task
from scripts import p0_task5_profiles as profiles


class FrozenTaskTests(unittest.TestCase):
    def test_frozen_manifest_detects_changes(self):
        frozen, prior = Path("C:/fixture/frozen"), Path("C:/fixture/prior")
        names = ("solver.py", "runtime_manifest.json", "run_contract.json", "build_record.json",
                 "task4_summary.json", "task4_audit.json")
        hashes = {name: f"digest-{name}" for name in names}
        manifest = {"files_sha256": hashes, "freeze_deadline_utc": "2026-11-06T03:02:18+00:00"}

        def read_text(path, **_kwargs):
            if path == frozen / "manifest.json":
                return json.dumps(manifest)
            if path == prior / "summary.json":
                return json.dumps({"freeze_deadline_utc": manifest["freeze_deadline_utc"]})
            raise AssertionError(path)

        def digest(path):
            if path == task.runtime.MANIFEST:
                return hashes["runtime_manifest.json"]
            return hashes[path.name]

        with patch.object(task, "FROZEN", frozen), patch.object(task, "PRIOR", prior), \
                patch.object(Path, "read_text", autospec=True, side_effect=read_text), \
                patch.object(Path, "read_bytes", autospec=True, return_value=b"pass"), \
                patch.object(task, "sha", side_effect=digest):
            actual, source = task._frozen()
            self.assertEqual(actual, manifest)
            self.assertEqual(source, b"pass")
            hashes.pop("build_record.json")
            with self.assertRaises(ValueError):
                task._frozen()

    def test_profile_plan_has_fifteen_distinct_authorized_targets(self):
        source = Path("C:/fixture/python")
        manifest = {"source": str(source), "file_count": 2362, "bytes_per_identity": 68546780}
        with patch.object(profiles.runtime, "_source_root", return_value=source), \
                patch.object(profiles.setup, "_manifest", return_value=(manifest, "digest")):
            plan = profiles.build_plan()
        self.assertEqual(len({item["name"] for item in plan["targets"]}), 15)
        self.assertEqual(plan["total_runtime_files"], 15 * plan["runtime_files_per_profile"])

    def test_verification_gate_rejects_changed_executor(self):
        first = {"event": "sources", "script_sha256": "script", "plan_sha256": "plan",
                 "executor_sha256": "executor", "frozen_manifest_sha256": "frozen"}
        events = [first, {"event": "result", "result": {"passed": True}}]

        def digest(path):
            if path == task.profiles_setup.PLAN:
                return "plan"
            if path == task.FROZEN / "manifest.json":
                return "frozen"
            return "script" if path.name == "p0_task5.py" else "executor"

        with patch.object(task.sandbox, "_read_events", return_value=events), patch.object(task, "sha", side_effect=digest):
            task._verification_gate()
            first["executor_sha256"] = "changed"
            with self.assertRaises(ValueError):
                task._verification_gate()

    def test_resource_wait_retries_without_staging_on_other_errors(self):
        profile = {"profile_folder": r"C:\Test\AC", "profile_name": "fixture"}
        slot = {"slot": 0, "logical_processor": 16}
        with patch.object(task, "_remaining", return_value=120), patch.object(task.sandbox, "_SlotGuard"), \
                patch.object(task.sandbox, "_run_program", side_effect=[OSError("资源检查不满足 P0 条件"), {"reason": "exited"}]) as run, \
                patch.object(task.time, "sleep"):
            result = task._solve(profile, slot, b"pass", b"{}")
            self.assertEqual(result["reason"], "exited")
            self.assertEqual(run.call_count, 2)
        with patch.object(task, "_remaining", return_value=120), patch.object(task.sandbox, "_SlotGuard"), \
                patch.object(task.sandbox, "_run_program", side_effect=OSError("other")) as run:
            with self.assertRaises(OSError):
                task._solve(profile, slot, b"pass", b"{}")
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
