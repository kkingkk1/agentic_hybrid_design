"""验证P0实际入口的验收门禁和源码只读锁。"""

import hashlib
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, mock_open, patch

from scripts import p0_sandbox_exec as sandbox


@unittest.skipUnless(os.name == "nt", "P0受限执行器仅适用于Windows")
class P0SandboxExecTests(unittest.TestCase):
    def test_gate_refuses_to_run_without_matching_probe(self):
        with patch.object(sandbox, "_slot_evidence", return_value={}), patch.object(Path, "glob", return_value=[]):
            with self.assertRaises(OSError):
                sandbox._require_gate()

    def test_gate_refuses_to_run_without_matching_file_fixture(self):
        with patch.object(sandbox, "_require_probe_gate", return_value={}), patch.object(Path, "glob", return_value=[]):
            with self.assertRaisesRegex(OSError, "源码文件探针"):
                sandbox._require_gate()

    def test_missing_gate_stops_before_creating_candidate_directory(self):
        with patch.object(sandbox, "_require_gate", side_effect=OSError("not ready")), \
                patch.object(Path, "mkdir") as mkdir:
            with self.assertRaises(OSError):
                sandbox.run_candidate("unused", 0, b"pass", b"", build=True)
            mkdir.assert_not_called()

    def test_invalid_source_and_build_input_stop_before_profile_access(self):
        with patch.object(sandbox, "_require_gate", return_value={}), \
                patch.object(sandbox, "_profile") as profile:
            for source, payload in ((b"", b""), (b"pass", b"unexpected")):
                with self.subTest(source=source), self.assertRaises(ValueError):
                    sandbox.run_candidate("unused", 0, source, payload, build=True)
            profile.assert_not_called()

    def test_source_lock_denies_write_open_without_modifying_file(self):
        plan = sandbox._slot_evidence()
        profile = sandbox._profile(plan, plan["targets"][0]["name"])
        source = Path(profile["profile_folder"]) / sandbox.identity.RUNTIME_DIR / "Lib" / "json" / "tool.py"
        before = sandbox.runtime._sha256(source)
        with sandbox._LockedSource(source):
            with self.assertRaises(PermissionError):
                with source.open("r+b"):
                    pass
        self.assertEqual(sandbox.runtime._sha256(source), before)

    def test_same_slot_cannot_be_allocated_by_another_thread(self):
        result = []

        def attempt():
            try:
                with sandbox._SlotGuard(0):
                    result.append("acquired")
            except OSError:
                result.append("blocked")

        with sandbox._SlotGuard(0):
            worker = threading.Thread(target=attempt)
            worker.start()
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["blocked"])

    def test_probe_cannot_supply_an_arbitrary_mode(self):
        profile = {"profile_folder": r"C:\Test\AC"}
        with self.assertRaises(ValueError):
            sandbox._run_program(profile, {"logical_processor": 1}, Path("unused"), b"", build=False,
                                 probe_mode="candidate", other={})

    def test_existing_identity_claim_stops_before_staging_or_launch(self):
        profile = {"profile_folder": r"C:\Test\AC"}
        mapping = {"workers": [{"slot": 0, "logical_processor": 16}]}

        def admit(*_args, prepare_source, **_kwargs):
            return prepare_source()

        with patch.object(sandbox, "_require_gate", return_value={}), \
                patch.object(sandbox.job, "read_windows_topology", return_value=()), \
                patch.object(sandbox.job, "select_mapping", return_value=mapping), \
                patch.object(sandbox, "_profile", return_value=profile), \
                patch.object(sandbox, "_SlotGuard"), patch.object(sandbox.runtime, "_safe_stat"), \
                patch.object(Path, "mkdir") as mkdir, \
                patch.object(Path, "open", side_effect=FileExistsError("already used")), \
                patch.object(sandbox, "_run_program", side_effect=admit) as launch:
            with self.assertRaises(FileExistsError):
                sandbox.run_candidate("P0Task3Probe_20261105_03", 0, b"pass", b"", build=True)
            self.assertEqual(mkdir.call_count, 1)  # 仅检查记录目录；未创建候选目录。
            launch.assert_called_once()

    def test_resource_rejection_does_not_consume_identity(self):
        profile = {"profile_folder": r"C:\Test\AC"}
        mapping = {"workers": [{"slot": 0, "logical_processor": 16}]}
        with patch.object(sandbox, "_require_gate", return_value={}), \
                patch.object(sandbox.job, "read_windows_topology", return_value=()), \
                patch.object(sandbox.job, "select_mapping", return_value=mapping), \
                patch.object(sandbox, "_profile", return_value=profile), \
                patch.object(sandbox, "_SlotGuard"), patch.object(sandbox, "_LockedSource"), \
                patch.object(sandbox.runtime, "_safe_stat"), \
                patch.object(sandbox.runtime, "_sha256", return_value=hashlib.sha256(b"pass").hexdigest()), \
                patch.object(Path, "mkdir") as mkdir, patch.object(Path, "open", mock_open()), \
                patch.object(sandbox, "_run_program", side_effect=OSError("resources unavailable")):
            with self.assertRaisesRegex(OSError, "resources unavailable"):
                sandbox.run_candidate("P0Task3Probe_20261105_03", 0, b"pass", b"", build=True)
            mkdir.assert_not_called()

    def test_program_resource_gate_precedes_source_preparation(self):
        prepare = Mock()
        profile = {"profile_folder": r"C:\Test\AC"}
        with patch.object(sandbox.job, "_resource_gate", side_effect=OSError("resources unavailable")):
            with self.assertRaisesRegex(OSError, "resources unavailable"):
                sandbox._run_program(profile, {"logical_processor": 16}, Path("unused"), b"", build=True,
                                     prepare_source=prepare, expected_source_sha="expected")
        prepare.assert_not_called()

    def test_admitted_program_can_stage_and_lock_its_source(self):
        profile = {"profile_folder": r"C:\Test\AC"}
        mapping = {"workers": [{"slot": 0, "logical_processor": 16}]}
        digest = hashlib.sha256(b"pass").hexdigest()
        file_open = mock_open()

        def admit(*_args, prepare_source, expected_source_sha, **_kwargs):
            self.assertEqual(expected_source_sha, digest)
            lock = prepare_source()
            lock.__exit__(None, None, None)
            return {"reason": "exited"}

        with patch.object(sandbox, "_require_gate", return_value={}), \
                patch.object(sandbox.job, "read_windows_topology", return_value=()), \
                patch.object(sandbox.job, "select_mapping", return_value=mapping), \
                patch.object(sandbox, "_profile", return_value=profile), \
                patch.object(sandbox, "_SlotGuard"), patch.object(sandbox, "_LockedSource") as lock, \
                patch.object(sandbox.runtime, "_safe_stat"), patch.object(sandbox.runtime, "_sha256", return_value=digest), \
                patch.object(Path, "mkdir"), patch.object(Path, "open", file_open), \
                patch.object(sandbox, "_run_program", side_effect=admit):
            result = sandbox.run_candidate("P0Task3Probe_20261105_03", 0, b"pass", b"", build=True)
        self.assertEqual(result["source_sha256"], digest)
        file_open.return_value.__enter__.return_value.write.assert_any_call(b"pass")
        lock.return_value.__enter__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
