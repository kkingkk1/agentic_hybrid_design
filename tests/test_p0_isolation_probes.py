"""核验任务3探针的边界、失败门禁和已实现的作业限制。"""

import copy
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, mock_open, patch
import uuid

from scripts import p0_etw_pid_probe as etw
from scripts import p0_etw_batch_probe as batch
from scripts import p0_job_probe as job
from scripts import p0_job_privilege_probe as privilege_probe
from scripts import p0_sandbox_runtime as sandbox_runtime
from scripts import p0_elevated_ws_probe as elevated_ws
from scripts import p0_named_job_probe as named_job
from scripts import p0_appcontainer_probe as appcontainer
from scripts import p0_appcontainer_boundaries_probe as boundaries


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "任务3探针仅适用于 Windows")
class P0IsolationProbeTests(unittest.TestCase):
    def test_native_structure_layout_matches_64_bit_windows(self):
        self.assertEqual(ctypes.sizeof(etw.TraceProperties), 120)
        self.assertEqual(ctypes.sizeof(etw.TraceLogfile), 448)
        self.assertEqual(ctypes.sizeof(etw.EventRecord), 112)
        self.assertEqual(ctypes.sizeof(etw.EnableParameters), 48)
        self.assertEqual(ctypes.sizeof(job.MemoryStatus), 64)

    def test_pid_filter_contains_only_requested_process(self):
        observed = {}

        class FakeAdvapi:
            @staticmethod
            def EnableTraceEx2(trace, provider, control, level, keyword, match_all, timeout, parameters):
                parsed = ctypes.cast(parameters, ctypes.POINTER(etw.EnableParameters)).contents
                descriptor = parsed.filters[0]
                observed.update({"count": parsed.filter_count, "type": descriptor.type,
                                 "size": descriptor.size,
                                 "pid": ctypes.cast(descriptor.ptr, ctypes.POINTER(etw.U32)).contents.value})
                return 0

        provider = etw.GUID.from_uuid(uuid.UUID("22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"))
        self.assertEqual(etw._enable_pid(FakeAdvapi(), etw.U64(1), provider, 12345, 0x20), 0)
        self.assertEqual(observed, {"count": 1, "type": 0x80000004, "size": 4, "pid": 12345})

    def test_payload_predicates_are_limited_to_distinct_valid_pids(self):
        predicates = etw._payload_predicates(list(range(1, 9)))
        self.assertEqual([(item.name, item.operator, item.value) for item in predicates],
                         [("ProcessID", 0, str(pid)) for pid in range(1, 9)])
        for invalid in ([], list(range(1, 10)), [1, 1], [0], [-1], [True], [2**32]):
            with self.subTest(pids=invalid), self.assertRaises(ValueError):
                etw._payload_predicates(invalid)

    def test_eight_pid_payload_filters_build_without_enabling_kernel_provider(self):
        observed = {}

        class FakeAdvapi:
            @staticmethod
            def EnableTraceEx2(trace, provider, control, level, keyword, match_all, timeout, parameters):
                parsed = ctypes.cast(parameters, ctypes.POINTER(etw.EnableParameters)).contents
                observed["filter_types"] = [parsed.filters[index].type for index in range(parsed.filter_count)]
                event_filter = ctypes.cast(parsed.filters[1].ptr, ctypes.POINTER(etw.EventIdFilter)).contents
                observed["event_ids"] = list(event_filter.ids[:event_filter.count])
                return 0

        provider = etw.GUID.from_uuid(etw.KERNEL_PROCESS)
        tdh = ctypes.WinDLL("tdh", use_last_error=True)
        create = tdh.TdhCreatePayloadFilter
        create.argtypes = [ctypes.POINTER(etw.GUID), ctypes.POINTER(etw.EventDescriptor), ctypes.c_uint8,
                           etw.U32, ctypes.POINTER(etw.PayloadPredicate), ctypes.POINTER(ctypes.c_void_p)]
        create.restype = etw.U32
        intercepted_create = MagicMock(side_effect=create)
        proxy = SimpleNamespace(TdhCreatePayloadFilter=intercepted_create,
                                TdhAggregatePayloadFilters=tdh.TdhAggregatePayloadFilters,
                                TdhCleanupPayloadEventFilterDescriptor=tdh.TdhCleanupPayloadEventFilterDescriptor,
                                TdhDeletePayloadFilter=tdh.TdhDeletePayloadFilter)
        with patch.object(etw.ctypes, "WinDLL", return_value=proxy):
            result = etw._enable_payload(FakeAdvapi(), etw.U64(1), provider, list(range(1, 9)))
        self.assertEqual(result["create_filter_status"], [0, 0])
        self.assertEqual(result["aggregate_status"], 0)
        self.assertEqual(result["kernel_enable_status"], 0)
        self.assertEqual(result["aggregate_cleanup_status"], 0)
        self.assertEqual(result["filter_cleanup_status"], [0, 0])
        self.assertEqual(observed, {"filter_types": [0x80000100, 0x80000200], "event_ids": [3]})
        self.assertEqual([(call.args[2], call.args[3]) for call in intercepted_create.call_args_list],
                         [(1, 8), (1, 8)])  # EventMatchANY：任一目标 PID 匹配即可。

    def test_batch_partitions_sixteen_distinct_processes(self):
        self.assertEqual(batch._partitions(list(range(1, 17))), [list(range(1, 9)), list(range(9, 17))])
        for invalid in ([], list(range(1, 16)), list(range(1, 16)) + [1], list(range(1, 16)) + [True]):
            with self.subTest(pids=invalid), self.assertRaises(ValueError):
                batch._partitions(invalid)

    def test_batch_refuses_to_start_without_elevated_token(self):
        shell = MagicMock()
        shell.IsUserAnAdmin.return_value = 0
        with patch.object(batch.ctypes, "WinDLL", return_value=shell), \
                patch.object(batch.job, "_resource_gate") as gate:
            result = batch.run_probe()
        self.assertFalse(result["passed"])
        gate.assert_not_called()

    def test_batch_cleans_owned_workers_and_sessions_if_second_session_fails(self):
        created_jobs, stopped_sessions = [], []

        class FakeProcess:
            def __init__(self, pid):
                self.pid, self.returncode = pid, None
                self.stdout, self.stderr = io.BytesIO(), io.BytesIO()

            def poll(self):
                return self.returncode

            def communicate(self, timeout):
                self.returncode = 1
                self.stdout.close()
                self.stderr.close()
                return b"", b""

            def kill(self):
                self.returncode = 1

        class FakeJob:
            def __init__(self, logical):
                self.logical, self.process, self.closed = logical, None, False
                created_jobs.append(self)

            def start_thread_probe_suspended(self, hold_ms):
                self.process = FakeProcess(1000 + self.logical)
                return self.process

            def terminate(self):
                self.process.returncode = 1

            def accounting(self):
                return {"active_processes": 0}

            def close(self):
                self.closed = True

        class FakeSession:
            count = 0

            def __init__(self, advapi, pids, control_id, failure, sink):
                FakeSession.count += 1
                self.number = FakeSession.count
                self.name = f"P0Task3-owned-{self.number}"
                self.result = {}

            def start(self, control_guid):
                if self.number == 2:
                    raise OSError("simulated provider failure")

            def stop(self):
                stopped_sessions.append(self.number)

        shell = MagicMock()
        shell.IsUserAnAdmin.return_value = 1
        advapi = MagicMock()
        advapi.EventRegister.return_value = 0
        advapi.EventUnregister.return_value = 0
        slots = [{"slot": index, "logical_processor": index} for index in range(16)]
        with patch.object(batch.ctypes, "WinDLL", return_value=shell), \
                patch.object(batch.job, "_resource_gate", return_value={}), \
                patch.object(batch.job, "_available_memory", return_value=20 * 1024**3), \
                patch.object(batch, "read_windows_topology", return_value=()), \
                patch.object(batch, "select_mapping", return_value={"workers": slots}), \
                patch.object(batch.etw, "_configure_api", return_value=(advapi, None)), \
                patch.object(batch.job, "_ProbeJob", FakeJob), \
                patch.object(batch, "_FilteredSession", FakeSession), \
                patch.object(batch.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"")):
            result = batch.run_probe()
        self.assertFalse(result["passed"])
        self.assertIn("simulated provider failure", result["error"])
        self.assertEqual(stopped_sessions, [1, 2])
        self.assertEqual(len(created_jobs), 16)
        self.assertTrue(all(item.closed and item.process.returncode == 1 for item in created_jobs))
        self.assertEqual(result["cleanup_errors"], [])

    def test_batch_callback_rejects_foreign_or_unknown_events(self):
        failure = threading.Event()
        session = batch._FilteredSession(None, list(range(1, 9)), uuid.uuid4(), failure, lambda _: None)
        record = etw.EventRecord()
        record.header.provider = etw.GUID.from_uuid(etw.KERNEL_PROCESS)
        record.header.descriptor.id = 3
        record.header.descriptor.version = 0
        data = ctypes.create_string_buffer(struct.pack("<II", 1, 101))
        record.data = ctypes.addressof(data)
        record.data_length = 8
        session.callback(ctypes.byref(record))
        self.assertEqual(session.tids[1], {101})
        self.assertFalse(failure.is_set())
        foreign = ctypes.create_string_buffer(struct.pack("<II", 99999, 99998))
        record.data = ctypes.addressof(foreign)
        session.callback(ctypes.byref(record))
        self.assertTrue(failure.is_set())
        self.assertEqual(session.result["foreign_events"], 1)
        self.assertNotIn(99999, session.tids)
        failure.clear()
        record.header.descriptor.version = 2
        session.callback(ctypes.byref(record))
        self.assertTrue(failure.is_set())
        self.assertEqual(session.result["invalid_events"], 1)

    def test_etw_passes_only_with_both_threads_and_complete_evidence(self):
        statuses = ("register_status", "start_status", "control_enable_status", "control_write_status",
                    "kernel_enable_status", "resume_status", "worker_exit", "stop_status", "close_status",
                    "unregister_status", "session_enumeration_status")
        valid = {name: 0 for name in statuses}
        valid.update({"mode": "payload", "control_events": 1, "target_pid": 10,
                      "worker": {"pid": 10, "ordinary_tid": 11, "hidden_tid": 12},
                      "foreign_events": 0, "invalid_events": 0, "events_lost": 0,
                      "realtime_buffers_lost": 0, "consumer_events_lost": 0,
                      "consumer_finished": True, "process_trace_status": [0], "session_gone": True,
                      "create_filter_status": [0, 0], "aggregate_status": 0,
                      "aggregate_cleanup_status": 0, "filter_cleanup_status": [0, 0]})
        self.assertTrue(etw._probe_passed(valid, {11, 12}, []))
        self.assertFalse(etw._probe_passed(valid, {11}, []))
        self.assertFalse(etw._probe_passed(valid, {11, 12}, ["callback error"]))
        for field, value in (("kernel_enable_status", 5), ("control_events", 0),
                             ("events_lost", 1), ("foreign_events", 1), ("session_gone", False),
                             ("filter_cleanup_status", [0, 5])):
            with self.subTest(field=field):
                altered = copy.deepcopy(valid)
                altered[field] = value
                self.assertFalse(etw._probe_passed(altered, {11, 12}, []))

    def test_probe_worker_cannot_be_replaced_by_candidate_command(self):
        probe_job = object.__new__(job._ProbeJob)
        with self.assertRaises(ValueError):
            probe_job.start_worker("candidate.py")

    def test_missing_worker_evidence_does_not_pass_job_check(self):
        self.assertFalse(job._valid({"active_processes": 0, "mode": "identity", "worker": None}))
        self.assertFalse(job._valid({"active_processes": 0, "mode": "memory", "worker": None}))
        self.assertFalse(job._valid({"active_processes": 0, "mode": "child", "reason": "exited",
                                     "exit_code": 0, "worker": {"blocked": True, "winerror": 2}}))

    def test_late_output_cannot_pass_even_with_zero_exit_code(self):
        result = {"active_processes": 0, "mode": "identity", "reason": "exited", "exit_code": 0,
                  "elapsed_seconds": 15.001, "logical_processor": 16, "pid": 99,
                  "worker": {"pid": 99, "affinity": 1 << 16, "priority": 0x20,
                             "working_set_bytes": 10}}
        self.assertFalse(job._valid(result))

    def test_etw_child_environment_omits_unrelated_secrets(self):
        with patch.dict(os.environ, {"P0_FAKE_SECRET": "not-a-real-token"}):
            environment = etw._probe_environment()
        self.assertNotIn("P0_FAKE_SECRET", environment)
        self.assertEqual(set(environment), {"SystemRoot", "WINDIR", "PATH"})

    def test_etw_record_is_new_and_captures_session_before_result(self):
        file_mock = mock_open()

        def fake_probe(mode, sink):
            self.assertEqual(mode, "payload")
            sink({"event": "session_started", "session": "P0Task3-owned"})
            return {"passed": True}

        with patch.object(sys, "argv", ["p0_etw_pid_probe.py", "--mode", "payload", "--record",
                                       "p0_task3_etw_test.jsonl"]), \
                patch.object(etw, "run_probe", side_effect=fake_probe), \
                patch.object(Path, "open", file_mock), patch.object(sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(etw.main(), 0)
        self.assertEqual(file_mock.call_args.args[0], "x")
        events = [json.loads(call.args[0]) for call in file_mock().write.call_args_list]
        self.assertEqual([event["event"] for event in events], ["session_started", "result"])

    def test_etw_record_rejects_path_traversal(self):
        with patch.object(sys, "argv", ["p0_etw_pid_probe.py", "--record", "../other.jsonl"]), \
                patch.object(sys, "stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as caught:
                etw.main()
        self.assertEqual(caught.exception.code, 2)

    def test_resource_gate_stops_low_memory_or_sustained_high_cpu(self):
        with patch.object(job, "_available_memory", return_value=15 * 1024**3):
            with self.assertRaises(OSError):
                job._resource_gate()
        with patch.object(job, "_available_memory", return_value=20 * 1024**3), \
                patch.object(job, "_cpu_sample", side_effect=[90.0, 90.0]):
            with self.assertRaises(OSError):
                job._resource_gate()
        with patch.object(job, "_available_memory", return_value=20 * 1024**3), \
                patch.object(job, "_cpu_sample", side_effect=[90.0, 10.0]):
            self.assertEqual(job._resource_gate()["cpu_percent_samples"], [90.0, 10.0])

    def test_controlled_worker_creates_two_distinct_threads(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts" / "p0_thread_probe.py")],
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        payload = json.loads(result.stdout)
        self.assertGreater(payload["ordinary_tid"], 0)
        self.assertGreater(payload["hidden_tid"], 0)
        self.assertNotEqual(payload["ordinary_tid"], payload["hidden_tid"])

    def test_controlled_thread_worker_can_be_assigned_before_resume(self):
        if job._available_memory() < 16 * 1024**3:
            self.skipTest("可用内存低于16 GiB。")
        probe_job = job._ProbeJob(16)
        process = None
        try:
            process = probe_job.start_thread_probe_suspended()
            self.assertIsNone(process.poll())
            probe_job.resume(process)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
            self.assertEqual(json.loads(stdout)["pid"], process.pid)
        finally:
            if process is not None and process.poll() is None:
                probe_job.terminate()
                process.communicate(timeout=5)
            probe_job.close()

    def test_appcontainer_launch_control_does_not_create_profile(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "p0_appcontainer_probe.py"),
                                 "--control"], capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertFalse(payload["profile_created"])
        self.assertFalse(payload["is_appcontainer"])

    def test_appcontainer_create_requires_specific_name_and_new_record(self):
        invalid_arguments = (
            ["--create-profile", "P0Task3Probe_20261105_01"],
            ["--retry-profile-from", "p0_task3_appcontainer_test.jsonl"],
            ["--retry-profile-from", "../other.jsonl", "--record", "p0_task3_appcontainer_test.jsonl"],
            ["--create-profile", "../existing", "--record", "p0_task3_appcontainer_test.jsonl"],
            ["--create-profile", "P0Task3Probe_２０２６１１０５_０１", "--record", "p0_task3_appcontainer_test.jsonl"],
            ["--create-profile", "P0Task3Probe_20261105_01", "--record", "../other.jsonl"],
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments), \
                    patch.object(sys, "argv", ["p0_appcontainer_probe.py", *arguments]), \
                    patch.object(sys, "stderr", new_callable=io.StringIO), \
                    patch.object(appcontainer, "run_probe") as probe:
                with self.assertRaises(SystemExit) as caught:
                    appcontainer.main()
                self.assertEqual(caught.exception.code, 2)
                probe.assert_not_called()

    def test_appcontainer_profile_collision_never_launches_or_reuses_it(self):
        libraries = {name: MagicMock() for name in ("kernel32", "userenv", "advapi32", "ole32", "ntdll")}
        libraries["userenv"].CreateAppContainerProfile.return_value = -2147024713  # HRESULT 0x800700B7
        events = []
        with patch.object(appcontainer.ctypes, "WinDLL", side_effect=lambda name, **_: libraries[name]):
            result = appcontainer.run_probe(profile_name="P0Task3Probe_20261105_01", sink=events.append)
        self.assertFalse(result["passed"])
        self.assertFalse(result["profile_created"])
        self.assertEqual(result["create_profile_status"], 0x800700B7)
        self.assertEqual([event["event"] for event in events], ["profile_create_attempt"])
        libraries["kernel32"].CreateProcessW.assert_not_called()
        libraries["userenv"].DeriveAppContainerSidFromAppContainerName.assert_not_called()

    def test_appcontainer_retry_requires_matching_complete_creation_record(self):
        name = "P0Task3Probe_20261105_01"
        details = {"profile_name": name, "profile_sid": "S-1-15-2-123", "profile_folder": r"C:\Test\AC"}
        events = [{"event": "source", "sha256": "test"},
                  {"event": "profile_create_attempt", "profile_name": name},
                  {"event": "profile_created", "profile_name": name},
                  {"event": "profile_details", **details},
                  {"event": "result", "result": {**details, "profile_created": True}}]
        raw = b"\n".join(json.dumps(item).encode("utf-8") for item in events)
        with patch.object(Path, "read_bytes", return_value=raw):
            profile = appcontainer._recorded_profile("p0_task3_appcontainer_test.jsonl")
        self.assertEqual({key: profile[key] for key in details}, details)
        self.assertEqual(profile["source_record"], "p0_task3_appcontainer_test.jsonl")
        altered = copy.deepcopy(events)
        altered[-1]["result"]["profile_sid"] = "S-1-15-2-456"
        raw = b"\n".join(json.dumps(item).encode("utf-8") for item in altered)
        with patch.object(Path, "read_bytes", return_value=raw), self.assertRaises(ValueError):
            appcontainer._recorded_profile("p0_task3_appcontainer_test.jsonl")
        with self.assertRaises(ValueError):
            appcontainer._recorded_profile("../test.jsonl")

    def test_appcontainer_child_environment_excludes_unrelated_values(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Test\Local", "P0_FAKE_SECRET": "not-a-real-token"}):
            block = appcontainer._child_environment(r"C:\Windows")
        values = dict(item.split("=", 1) for item in block.split("\0") if item)
        self.assertEqual(set(values), {"LOCALAPPDATA", "PATH", "SystemRoot", "WINDIR"})
        self.assertNotIn("P0_FAKE_SECRET", block)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(OSError):
            appcontainer._child_environment(r"C:\Windows")

    def test_unknown_lpac_state_never_passes_an_lpac_probe(self):
        self.assertTrue(appcontainer._lpac_mode_acceptable(False, None))
        self.assertFalse(appcontainer._lpac_mode_acceptable(True, None))
        self.assertTrue(appcontainer._lpac_mode_acceptable(True, True))
        self.assertTrue(appcontainer._lpac_mode_acceptable(False, False))
        self.assertFalse(appcontainer._lpac_mode_acceptable(True, False))
        self.assertFalse(appcontainer._lpac_mode_acceptable(False, True))

    def test_boundary_commands_are_fixed_and_only_target_loopback(self):
        _, file_command = appcontainer._controlled_command(r"C:\Windows\System32", "fixture")
        self.assertIn(str(appcontainer.BOUNDARY_FIXTURE), file_command)
        _, command = appcontainer._controlled_command(r"C:\Windows\System32", "loopback", 12345)
        self.assertIn("http://127.0.0.1:12345/p0", command)
        for action, port in (("candidate", None), ("loopback", -1), ("loopback", True),
                             ("loopback", 65536), ("fixture", 80)):
            with self.subTest(action=action, port=port), self.assertRaises(ValueError):
                appcontainer._controlled_command(r"C:\Windows\System32", action, port)
        with self.assertRaises(ValueError):
            appcontainer.run_probe(action="fixture")

    def test_python_version_probe_refuses_a_different_interpreter(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Test\Local"}), \
                patch.object(sys, "executable", r"C:\Test\Local\Programs\Python\Python313\python.exe"):
            _, command = appcontainer._controlled_command(r"C:\Windows\System32", "python_version")
            self.assertIn("-I -B -V", command)
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Test\Local"}), \
                patch.object(sys, "executable", r"C:\Other\python.exe"), self.assertRaises(ValueError):
            appcontainer._controlled_command(r"C:\Windows\System32", "python_version")

    def test_own_fixture_command_requires_the_recorded_identity_and_folder(self):
        profile = {"profile_name": "P0Task3Probe_20261105_01", "profile_sid": "S-1-15-2-123",
                   "profile_folder": r"C:\Test\AC"}
        with patch.object(appcontainer, "_recorded_profile", return_value=profile):
            _, command = appcontainer._controlled_command(r"C:\Windows\System32", "own_fixture", profile=profile)
            self.assertIn(appcontainer.OWN_FIXTURE_NAME, command)
            with self.assertRaises(ValueError):
                appcontainer._controlled_command(r"C:\Windows\System32", "own_fixture",
                                                 profile={**profile, "profile_folder": r"C:\Other"})
            with self.assertRaises(ValueError):
                appcontainer._controlled_command(r"C:\Windows\System32", "own_fixture")

    def test_runtime_smoke_only_uses_the_recorded_profile_directory(self):
        profile = {"profile_name": "P0Task3Probe_20261105_01", "profile_sid": "S-1-15-2-123",
                   "profile_folder": r"C:\Test\AC"}
        with patch.object(appcontainer, "_recorded_profile", return_value=profile):
            _, command = appcontainer._controlled_command(r"C:\Windows\System32", "owned_python_smoke",
                                                          profile=profile)
            self.assertIn(appcontainer.RUNTIME_DIR, command)
            self.assertIn("-I -B -c", command)
            exe, direct = appcontainer._controlled_command(r"C:\Windows\System32", "owned_python_direct",
                                                            profile=profile)
            self.assertTrue(exe.endswith("python.exe"))
            self.assertIn("-I -B -c", direct)
            exe, combined = appcontainer._controlled_command(r"C:\Windows\System32", "owned_python_job",
                                                              profile=profile)
            self.assertTrue(exe.endswith("python.exe"))
            self.assertIn("P0_COMBINED_OK", combined)
            with self.assertRaises(ValueError):
                appcontainer._controlled_command(r"C:\Windows\System32", "owned_python_smoke",
                                                 profile={**profile, "profile_sid": "S-1-15-2-456"})

    def test_combined_evidence_requires_the_expected_pid_core_and_child_block(self):
        report = {"pid": 42, "affinity": 65536, "priority": 32, "child_error": 1816,
                  "invalid_rejected": True}
        line = "P0_COMBINED_OK " + json.dumps(report)
        self.assertTrue(appcontainer._combined_evidence(line, 42, 65536)["passed"])
        for key, value in (("pid", 43), ("affinity", 131072), ("priority", 64), ("child_error", 5),
                           ("invalid_rejected", False)):
            with self.subTest(key=key):
                altered = {**report, key: value}
                self.assertFalse(appcontainer._combined_evidence("P0_COMBINED_OK " + json.dumps(altered),
                                                                42, 65536)["passed"])
        self.assertFalse(appcontainer._combined_evidence(line + "\n" + line, 42, 65536)["passed"])
        self.assertFalse(appcontainer._combined_evidence("P0_COMBINED_OK invalid", 42, 65536)["passed"])

    def test_runtime_evidence_rejects_modules_from_outside_private_copy(self):
        profile = {"profile_folder": r"C:\Test\AC"}
        runtime = Path(profile["profile_folder"]) / appcontainer.RUNTIME_DIR
        modules = ("json", "math", "random", "decimal", "ctypes", "ssl", "sqlite3")
        report = {"version": [3, 13, 12], "executable": str(runtime / "python.exe"),
                  "origins": {name: str(runtime / "Lib" / f"{name}.py") for name in modules}}
        line = "P0_RUNTIME_OK " + json.dumps(report)
        self.assertTrue(appcontainer._runtime_evidence(line, profile)["passed"])
        report["origins"]["math"] = "built-in"
        self.assertTrue(appcontainer._runtime_evidence("P0_RUNTIME_OK " + json.dumps(report), profile)["passed"])
        report["origins"]["json"] = r"C:\Other\json.py"
        self.assertFalse(appcontainer._runtime_evidence("P0_RUNTIME_OK " + json.dumps(report), profile)["passed"])
        self.assertFalse(appcontainer._runtime_evidence("", profile)["passed"])

    def test_own_fixture_collision_never_starts_an_appcontainer(self):
        profile = {"profile_name": boundaries.PROFILE_NAME, "profile_folder": r"C:\Test\AC",
                   "source_record_sha256": "hash"}
        with patch.object(boundaries.job, "_resource_gate", return_value={}), \
                patch.object(boundaries.identity, "_recorded_profile", return_value=profile), \
                patch.object(Path, "open", side_effect=FileExistsError("fixture exists")), \
                patch.object(boundaries.identity, "run_probe") as launch:
            result = boundaries.run_own_fixture_probe()
        self.assertFalse(result["passed"])
        launch.assert_not_called()

    def test_cross_fixture_requires_two_distinct_recorded_identities(self):
        names = list(appcontainer.PROFILE_RECORDS)
        profiles = [{"profile_name": name, "profile_sid": "S-1-15-2-123"} for name in names]
        with patch.object(boundaries.job, "_resource_gate", return_value={}), \
                patch.object(boundaries.identity, "_recorded_profile", side_effect=profiles), \
                patch.object(Path, "open") as fixture:
            result = boundaries.run_cross_fixture_probe()
        self.assertFalse(result["passed"])
        self.assertIn("不独立", result["error"])
        fixture.assert_not_called()

    def test_privilege_probe_only_accepts_two_fixed_names(self):
        with self.assertRaises(ValueError):
            privilege_probe.run_probe("SeDebugPrivilege")
        arguments = ["p0_job_privilege_probe.py", "--privilege", "SeIncreaseBasePriorityPrivilege", "--record",
                     "p0_task3_job_privilege_test.json"]
        with patch.object(sys, "argv", arguments), \
                patch.object(Path, "open", side_effect=FileExistsError("record exists")), \
                patch.object(privilege_probe, "run_probe") as run:
            with self.assertRaises(FileExistsError):
                privilege_probe.main()
            run.assert_not_called()

    def test_runtime_manifest_rejects_outside_and_third_party_paths(self):
        self.assertEqual(sandbox_runtime._relative_path("Lib/json/__init__.py"), Path("Lib/json/__init__.py"))
        for invalid in ("../other", "/Lib/x", "Lib/../other", "Lib/site-packages/x.py", "Lib/__pycache__/x.py",
                        "Lib/foo.pyc", "python.exe/other", "Lib\\other"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                sandbox_runtime._relative_path(invalid)

    def test_runtime_copy_rejects_changed_manifest_before_destinations(self):
        with patch.object(sandbox_runtime, "build_manifest", return_value={"changed": True}), \
                patch.object(sandbox_runtime, "_destinations") as destinations:
            with self.assertRaises(ValueError):
                sandbox_runtime.copy_runtime({"changed": False}, lambda _: None)
        destinations.assert_not_called()

    def test_runtime_resume_requires_a_complete_verified_first_copy_record(self):
        destination = Path(r"C:\Test\p0_runtime_20261105_01")
        manifest = {"file_count": 1}
        with patch.object(Path, "read_bytes", side_effect=[b'{"event":"sources"}\n', b"manifest"]):
            with self.assertRaises(ValueError):
                sandbox_runtime._verify_resume_record(destination, manifest)
        with self.assertRaises(ValueError):
            sandbox_runtime.copy_runtime({}, lambda _: None, direct=True)

    def test_elevated_working_set_probe_never_starts_without_admin(self):
        shell = MagicMock()
        shell.IsUserAnAdmin.return_value = 0
        with patch.object(elevated_ws.ctypes, "WinDLL", return_value=shell), \
                patch.object(elevated_ws, "_apis") as apis:
            result = elevated_ws.run_probe()
        self.assertFalse(result["passed"])
        apis.assert_not_called()

    def test_working_set_pass_requires_restricted_token_hard_limit_and_peak(self):
        limit = 64 * 1024 * 1024
        result = {"exit_code": 0, "is_appcontainer": True, "sid_matches": True, "capability_count": 0,
                  "target_elevation": 0, "target_elevation_type": 3, "target_user_matches": True,
                  "active_processes": 0, "host_peak_before_resume": 1024, "host_peak_after_exit": limit,
                  "worker": {"limit": limit, "before": {"min": 1048576, "max": limit, "flags": 4},
                             "after": {"min": 1048576, "max": limit, "flags": 4}, "disable_success": False,
                             "peak_working_set": limit}}
        self.assertTrue(elevated_ws._worker_passed(result, 64))
        for field, value in (("target_elevation", 1), ("target_user_matches", False),
                             ("sid_matches", False), ("active_processes", 1)):
            with self.subTest(field=field):
                changed = copy.deepcopy(result)
                changed[field] = value
                self.assertFalse(elevated_ws._worker_passed(changed, 64))
        changed = copy.deepcopy(result)
        changed["worker"]["disable_success"] = True
        self.assertTrue(elevated_ws._worker_passed(changed, 64))  # 调用成功但回读未改变限制。
        for field, value in (("disable_success", None), ("peak_working_set", limit + 1)):
            with self.subTest(field=field):
                changed = copy.deepcopy(result)
                changed["worker"][field] = value
                self.assertFalse(elevated_ws._worker_passed(changed, 64))
        result["job_name_tested"] = True
        result["worker"].update({"job_open_success": False, "job_open_error": 5})
        self.assertTrue(elevated_ws._worker_passed(result, 64))
        result["worker"]["job_open_success"] = True
        self.assertFalse(elevated_ws._worker_passed(result, 64))

        limit512 = 512 * 1024 * 1024
        case512 = {"exit_code": 0, "is_appcontainer": True, "sid_matches": True, "capability_count": 0,
                   "target_elevation": 0, "target_elevation_type": 3, "target_user_matches": True,
                   "active_processes": 0, "host_peak_before_resume": 1024, "host_peak_after_exit": limit512,
                   "worker": {"limit": limit512, "before": {"min": 1048576, "max": limit512, "flags": 4},
                              "after": {"min": 1048576, "max": limit512, "flags": 4}, "disable_success": True,
                              "peak_working_set": limit512, "mapped_views": 95, "mapped_bytes": limit512 + 1}}
        self.assertTrue(elevated_ws._worker_passed(case512, 512))
        case512["worker"]["mapped_views"] = 1
        self.assertFalse(elevated_ws._worker_passed(case512, 512))

    def test_named_job_continues_after_small_diagnostic_excess_only_when_safe(self):
        limit = 64 * 1024 * 1024
        case = {"exit_code": 0, "active_processes": 0, "target_elevation": 0, "target_elevation_type": 3,
                "target_user_matches": True, "is_appcontainer": True, "sid_matches": True,
                "capability_count": 0, "host_peak_after_exit": limit + 8192,
                "worker": {"before": {"max": limit, "flags": 4}, "after": {"max": limit, "flags": 4},
                           "job_open_success": False, "job_open_error": 5}}
        self.assertTrue(named_job._safe_to_continue(case, 64))
        case["worker"]["after"]["flags"] = 8
        self.assertFalse(named_job._safe_to_continue(case, 64))

    def test_named_job_coordinator_rejects_wrong_names_and_elevated_parent(self):
        prefix = r"Local\P0Task3WS-" + "a" * 32
        self.assertTrue(named_job._names_valid([prefix + "-64", prefix + "-512"]))
        for names in ([prefix + "-64"], [prefix + "-64", prefix + "-64"],
                      [prefix + "-64", r"Local\P0Task3WS-" + "b" * 32 + "-512"],
                      ["existing-job", prefix + "-512"]):
            with self.subTest(names=names):
                self.assertFalse(named_job._names_valid(names))
        self.assertEqual(ctypes.sizeof(named_job.ShellExecuteInfo), 112)
        with patch.object(named_job, "_admin", return_value=True), \
                patch.object(named_job.ws, "_apis") as apis:
            self.assertFalse(named_job.run_probe()["passed"])
            apis.assert_not_called()

    def test_named_job_helper_requires_elevation_before_opening_jobs(self):
        prefix = r"Local\P0Task3WS-" + "a" * 32
        with patch.object(named_job, "_admin", return_value=False), \
                patch.object(named_job.ws, "_apis") as apis:
            result = named_job.helper([prefix + "-64", prefix + "-512"], lambda _: None)
        self.assertFalse(result["passed"])
        apis.assert_not_called()

    def test_working_set_probe_terminates_unassigned_suspended_process(self):
        kernel, ntdll, advapi = MagicMock(), MagicMock(), MagicMock()
        kernel.CreateJobObjectW.return_value = 11
        kernel.SetInformationJobObject.return_value = 1

        def query(_handle, kind, output, _size, _return_length):
            if kind == 9:
                limits = ctypes.cast(output, ctypes.POINTER(job.ExtendedLimits)).contents
                limits.basic.flags = 0x0001 | 0x0008 | 0x0010 | 0x0100 | 0x0200 | 0x2000
                limits.basic.max_ws = 64 * 1024 * 1024
            return 1

        def init(_attributes, _count, _flags, size):
            ctypes.cast(size, ctypes.POINTER(ctypes.c_size_t)).contents.value = 64
            return 1

        def create(*args):
            process = ctypes.cast(args[-1], ctypes.POINTER(appcontainer.ProcessInfo)).contents
            process.process, process.thread, process.pid = 55, 56, 57
            return 1

        def deny(*_args):
            ctypes.set_last_error(5)
            return 0

        kernel.QueryInformationJobObject.side_effect = query
        kernel.InitializeProcThreadAttributeList.side_effect = init
        kernel.UpdateProcThreadAttribute.return_value = 1
        kernel.AssignProcessToJobObject.side_effect = deny
        advapi.CreateProcessAsUserW.side_effect = create
        output = MagicMock()
        output.fileno.return_value = 5
        profile = {"profile_folder": r"C:\Test\AC"}
        with patch.object(Path, "open", return_value=output), \
                patch.object(elevated_ws.msvcrt, "get_osfhandle", return_value=22), \
                patch.object(elevated_ws.os, "set_handle_inheritable"):
            result = elevated_ws._case(kernel, ntdll, advapi, 33, ctypes.c_void_p(44), profile,
                                       "expected-user-hash", 16, 64, lambda _: None)
        self.assertFalse(result["passed"])
        kernel.TerminateProcess.assert_called_once_with(55, 1)
        kernel.TerminateJobObject.assert_not_called()
        self.assertFalse(result["resumed"])

    def test_named_working_set_case_keeps_parent_job_and_kills_unassigned_child(self):
        kernel, ntdll, advapi = MagicMock(), MagicMock(), MagicMock()

        def query(_handle, kind, output, _size, _return_length):
            if kind == 9:
                limits = ctypes.cast(output, ctypes.POINTER(job.ExtendedLimits)).contents
                limits.basic.flags = named_job.BASE_FLAGS | 1
                limits.basic.max_ws = 64 * 1024 * 1024
            return 1

        def init(_attributes, _count, _flags, size):
            ctypes.cast(size, ctypes.POINTER(ctypes.c_size_t)).contents.value = 64
            return 1

        def create(*args):
            process = ctypes.cast(args[-1], ctypes.POINTER(appcontainer.ProcessInfo)).contents
            process.process, process.thread, process.pid = 55, 56, 57
            return 1

        def deny(*_args):
            ctypes.set_last_error(5)
            return 0

        kernel.QueryInformationJobObject.side_effect = query
        kernel.InitializeProcThreadAttributeList.side_effect = init
        kernel.UpdateProcThreadAttribute.return_value = 1
        kernel.CreateProcessW.side_effect = create
        kernel.AssignProcessToJobObject.side_effect = deny
        output = MagicMock()
        output.fileno.return_value = 5
        profile = {"profile_folder": r"C:\Test\AC"}
        with patch.object(Path, "open", return_value=output), \
                patch.object(elevated_ws.msvcrt, "get_osfhandle", return_value=22), \
                patch.object(elevated_ws.os, "set_handle_inheritable"):
            result = elevated_ws._case(kernel, ntdll, advapi, None, ctypes.c_void_p(44), profile,
                                       "expected-user-hash", 16, 64, lambda _: None,
                                       preconfigured=11, output_version="02", job_name="owned-job")
        self.assertFalse(result["passed"])
        kernel.TerminateProcess.assert_called_once_with(55, 1)
        self.assertNotIn(unittest.mock.call(11), kernel.CloseHandle.call_args_list)
        advapi.CreateProcessAsUserW.assert_not_called()

    def test_boundary_rejects_different_profile_before_creating_fixture(self):
        with patch.object(boundaries.job, "_resource_gate", return_value={}), \
                patch.object(boundaries.identity, "_recorded_profile", return_value={"profile_name": "other"}), \
                patch.object(Path, "open") as fixture:
            result = boundaries.run_probe()
        self.assertFalse(result["passed"])
        self.assertIn("获授权的测试身份", result["error"])
        fixture.assert_not_called()

    def test_loopback_requires_both_host_controls_and_no_probe_connection(self):
        probe = {"identity_verified": True, "stage": "completed", "exit_code": 28}
        self.assertTrue(boundaries._loopback_blocked(probe, 0, 0, 1, 1, 2, []))
        self.assertFalse(boundaries._loopback_blocked(probe, 0, 1, 1, 1, 2, []))
        self.assertFalse(boundaries._loopback_blocked(probe, 0, 0, 1, 2, 3, []))
        self.assertFalse(boundaries._loopback_blocked(probe, 0, 0, 1, 1, 2, ["server_error"]))
        self.assertFalse(boundaries._loopback_blocked({**probe, "exit_code": 3}, 0, 0, 1, 1, 2, []))

    def test_appcontainer_record_is_created_before_profile_call(self):
        arguments = ["p0_appcontainer_probe.py", "--create-profile", "P0Task3Probe_20261105_01",
                     "--record", "p0_task3_appcontainer_test.jsonl"]
        with patch.object(sys, "argv", arguments), \
                patch.object(Path, "open", side_effect=FileExistsError("record exists")), \
                patch.object(appcontainer, "run_probe") as probe:
            with self.assertRaises(FileExistsError):
                appcontainer.main()
            probe.assert_not_called()

        file_mock = mock_open()

        def fake_probe(lpac, control, profile_name, sink):
            self.assertEqual((lpac, control, profile_name), (False, False, "P0Task3Probe_20261105_01"))
            sink({"event": "profile_create_attempt", "profile_name": profile_name})
            sink({"event": "profile_created", "profile_name": profile_name})
            return {"passed": True, "profile_created": True}

        with patch.object(sys, "argv", arguments), \
                patch.object(Path, "open", file_mock), patch.object(Path, "read_bytes", return_value=b"source"), \
                patch.object(appcontainer, "run_probe", side_effect=fake_probe), \
                patch.object(sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(appcontainer.main(), 0)
        self.assertEqual(file_mock.call_args.args[0], "x")
        events = [json.loads(call.args[0]) for call in file_mock().write.call_args_list]
        self.assertEqual([event["event"] for event in events],
                         ["source", "profile_create_attempt", "profile_created", "result"])

    def test_real_basic_job_limits_without_claiming_full_isolation(self):
        try:
            result = job.run_case("basic")
        except OSError as exc:
            if "暂停新探针" in str(exc):
                self.skipTest(str(exc))
            raise
        self.assertTrue(result["passed"], result)
        self.assertEqual([item["mode"] for item in result["results"]],
                         ["identity", "child", "memory", "stdout", "stderr"])
        self.assertIn("未核验工作集上限", result["scope"])


if __name__ == "__main__":
    unittest.main()
