"""检查固定探针入口、受限管道和结果判定。"""

import base64
import ctypes
import json
import os
import unittest
from unittest.mock import MagicMock, call, patch

from scripts import p0_restricted_probe as restricted


@unittest.skipUnless(os.name == "nt", "受限探针仅适用于 Windows")
class RestrictedProbeTests(unittest.TestCase):
    def setUp(self):
        names = list(restricted.identity.PROFILE_RECORDS)
        self.first = {"profile_name": names[0], "profile_sid": "S-1-15-2-111", "profile_folder": r"C:\Test\One"}
        self.second = {"profile_name": names[1], "profile_sid": "S-1-15-2-222", "profile_folder": r"C:\Test\Two"}

    def test_commands_reject_candidate_and_external_network_target(self):
        with self.assertRaises(ValueError):
            restricted._probe_args(self.first, self.second, "candidate")
        for port in (None, True, -1, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                restricted._probe_args(self.first, self.second, "loopback", port)
        command = restricted._probe_args(self.first, self.second, "loopback", 12345)
        self.assertEqual(command[-2], "127.0.0.1")
        self.assertEqual(command[-1], "12345")
        with patch.object(restricted, "_local_private_ipv4", return_value=["192.168.1.2"]):
            command = restricted._probe_args(self.first, self.second, "local_network", 12345, "192.168.1.2")
            self.assertEqual(command[-2:], ["192.168.1.2", "12345"])
            with self.assertRaises(ValueError):
                restricted._probe_args(self.first, self.second, "local_network", 12345, "8.8.8.8")
        own = restricted._probe_args(self.first, self.second, "read_own_runtime")
        other = restricted._probe_args(self.first, self.second, "read_other_runtime")
        self.assertTrue(own[-1].startswith(self.first["profile_folder"]))
        self.assertTrue(other[-1].startswith(self.second["profile_folder"]))

    def test_profile_must_match_existing_record_before_process_creation(self):
        records = restricted.identity.PROFILE_RECORDS
        lookup = {records[self.first["profile_name"]]: self.first, records[self.second["profile_name"]]: self.second}
        with patch.object(restricted.identity, "_recorded_profile", side_effect=lookup.get), \
                patch.object(restricted, "_windows_api") as api:
            altered = {**self.first, "profile_folder": r"C:\Other"}
            with self.assertRaises(ValueError):
                restricted._run_fixed(altered, self.second, {"logical_processor": 1}, "json")
            with self.assertRaises(ValueError):
                restricted._run_fixed(self.first, self.first, {"logical_processor": 1}, "json")
            with self.assertRaises(ValueError):
                restricted._run_fixed({"profile_name": "other"}, self.second, {"logical_processor": 1}, "json")
            api.assert_not_called()

    def test_reader_bounds_output_and_reports_excess(self):
        read_fd, write_fd = os.pipe()
        reader = restricted._PipeReader(read_fd, 1024)
        reader.thread.start()
        try:
            os.write(write_fd, b"x" * 1025)
        finally:
            os.close(write_fd)
        reader.thread.join(timeout=5)
        self.assertFalse(reader.thread.is_alive())
        self.assertTrue(reader.exceeded.is_set())
        self.assertEqual(len(reader.data), 1024)
        self.assertGreater(reader.observed, 1024)
        self.assertIsNotNone(reader.finished_monotonic)

    def test_pipe_creation_failure_closes_earlier_descriptors(self):
        records = restricted.identity.PROFILE_RECORDS
        lookup = {records[self.first["profile_name"]]: self.first, records[self.second["profile_name"]]: self.second}
        kernel, ntdll, advapi, userenv = (MagicMock() for _ in range(4))
        sid_string = ctypes.create_unicode_buffer(self.first["profile_sid"])

        def derive(_name, target):
            ctypes.cast(target, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(123)
            return 0

        def stringify(_sid, target):
            ctypes.cast(target, ctypes.POINTER(ctypes.c_wchar_p))[0] = ctypes.cast(sid_string, ctypes.c_wchar_p)
            return True

        userenv.DeriveAppContainerSidFromAppContainerName.side_effect = derive
        advapi.ConvertSidToStringSidW.side_effect = stringify
        with patch.object(restricted.identity, "_recorded_profile", side_effect=lookup.get), \
                patch.object(restricted.job, "_resource_gate", return_value={}), \
                patch.object(restricted, "_windows_api", return_value=(kernel, ntdll, advapi, userenv)), \
                patch.object(restricted.os, "pipe", side_effect=[(101, 102), OSError("pipe failed")]), \
                patch.object(restricted.os, "close") as close:
            with self.assertRaisesRegex(OSError, "pipe failed"):
                restricted._run_fixed(self.first, self.second, {"logical_processor": 1}, "json")
            close.assert_has_calls([call(101), call(102)], any_order=True)

    def test_basic_result_requires_both_limits_and_correct_output(self):
        encoded = lambda data: base64.b64encode(data).decode("ascii")
        payload = {"value": [1, 2]}
        results = {
            "build_valid": {"reason": "exited", "exit_code": 0},
            "build_invalid": {"reason": "exited", "exit_code": 1},
            "json": {"reason": "exited", "exit_code": 0, "stdout_b64": encoded(json.dumps(payload).encode())},
            "stdout_limit": {"reason": "stdout_limit", "stdout_bytes": 16385, "stdout_b64": encoded(b"x" * 16384)},
            "stderr_limit": {"reason": "stderr_limit", "stderr_bytes": 65537, "stderr_b64": encoded(b"x" * 65536)},
        }
        self.assertTrue(restricted._basic_checks(results, payload))
        changed = dict(results)
        changed["stderr_limit"] = {**results["stderr_limit"], "reason": "exited"}
        self.assertFalse(restricted._basic_checks(changed, payload))
        changed = dict(results)
        changed["json"] = {**results["json"], "stdout_b64": encoded(b"{}")}
        self.assertFalse(restricted._basic_checks(changed, payload))


if __name__ == "__main__":
    unittest.main()
