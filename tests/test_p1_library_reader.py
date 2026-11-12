"""验证 P1 读取器的真实条目、版本核对与路径边界。"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "p1_library_reader.py"
SPEC = importlib.util.spec_from_file_location("p1_library_reader", SCRIPT)
reader_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader_module)
ROOT = reader_module.DEFAULT_ROOT


class LibraryReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = reader_module.LibraryReader(ROOT)

    def test_catalog_includes_all_existing_entries_without_code(self):
        catalog = self.reader.catalog()
        for folder, prefix, key, id_key in (
            ("算法条目", "ALG-", "algorithms", "algorithm_id"),
            ("组合案例", "CASE-", "cases", "case_id"),
        ):
            directories = sorted(p for p in (ROOT / folder).iterdir()
                                 if p.is_dir() and p.name.startswith(prefix))
            self.assertTrue(directories)
            self.assertEqual([x[id_key] for x in catalog[key]], [p.name for p in directories])
            for candidate, directory in zip(catalog[key], directories):
                original = json.loads((directory / f"{directory.name}.json").read_bytes())
                self.assertNotIn("code", candidate)
                if key == "algorithms":
                    for field in ("category", "function", "summary"):
                        self.assertEqual(candidate[field], original[field])
                else:
                    self.assertEqual(candidate["description"], "".join(original["description"]))

    def test_selected_entries_return_full_material_in_requested_order(self):
        case, algorithm = self.reader.load(["CASE-001", "ALG-001"])
        case_dir = ROOT / "组合案例" / "CASE-001"
        alg_dir = ROOT / "算法条目" / "ALG-001"
        case_raw = (case_dir / "CASE-001.json").read_bytes()
        case_original = json.loads(case_raw)
        self.assertEqual(case["entry"]["case_id"], "CASE-001")
        self.assertEqual(case["entry"]["description"], "".join(case_original["description"]))
        self.assertEqual(case["entry"]["code"], "\n".join(case_original["code"]))
        self.assertEqual(case["json_file"]["sha256"], hashlib.sha256(case_raw).hexdigest())
        self.assertEqual(case["source"]["content"], (case_dir / "CASE-001.md").read_bytes().decode("utf-8"))

        original = json.loads((alg_dir / "ALG-001.json").read_bytes())
        code = original["code"]["files"][0]
        raw = (alg_dir / code["path"]).read_bytes()
        self.assertEqual(algorithm["entry"]["algorithm_id"], "ALG-001")
        self.assertEqual(algorithm["entry"]["description"], "".join(original["description"]))
        self.assertEqual(algorithm["entry"]["code"]["files"][0]["content"], raw.decode("utf-8"))
        self.assertEqual(code["sha256_lf"], hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
        self.assertEqual(algorithm["source"]["content"], (alg_dir / "ALG-001.md").read_bytes().decode("utf-8"))

    def test_invalid_unknown_and_duplicate_ids_fail(self):
        for ids in (["../ALG-001"], ["ALG-01"], ["CASE-001/extra"], ["ALG-999"],
                    ["ALG-001", "ALG-001"]):
            with self.subTest(ids=ids), self.assertRaises(reader_module.LibraryError):
                self.reader.load(ids)

    def test_algorithm_code_changes_and_case_json_changes_are_rejected(self):
        for relative, selected in (
            ("算法条目/ALG-001/split.py", "ALG-001"),
            ("组合案例/CASE-001/CASE-001.json", "CASE-001"),
        ):
            target = (ROOT / relative).resolve()
            original_read = reader_module._read_bytes

            def changed(path):
                raw = original_read(path)
                return raw + b"\n" if path == target else raw

            with self.subTest(selected=selected), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaisesRegex(reader_module.LibraryError, "SHA-256"):
                    self.reader.load([selected])

    def test_code_hash_normalizes_crlf_but_returns_original_text(self):
        target = (ROOT / "算法条目/ALG-001/split.py").resolve()
        original_read = reader_module._read_bytes

        def crlf(path):
            raw = original_read(path)
            return raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") if path == target else raw

        with patch.object(reader_module, "_read_bytes", crlf):
            item = self.reader.load(["ALG-001"])[0]["entry"]["code"]["files"][0]
        self.assertIn("\r\n", item["content"])
        self.assertEqual(item["content"], crlf(target).decode("utf-8"))

    def test_code_path_cannot_escape_its_entry(self):
        target = (ROOT / "算法条目/ALG-001/ALG-001.json").resolve()
        original_read = reader_module._read_bytes
        original = json.loads(original_read(target))
        for invalid in ("../outside.py", "..\\outside.py", "C:\\outside.py", "/outside.py"):
            altered = copy.deepcopy(original)
            altered["code"]["files"][0]["path"] = invalid

            def changed(path):
                return json.dumps(altered).encode("utf-8") if path == target else original_read(path)

            with self.subTest(path=invalid), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaises(reader_module.LibraryError):
                    self.reader.load(["ALG-001"])

    def test_resolved_code_path_outside_entry_is_rejected(self):
        target = ROOT / "算法条目/ALG-001/split.py"
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            if path == target:
                return original_resolve(PROJECT / "README.md", strict=True)
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            with self.assertRaisesRegex(reader_module.LibraryError, "路径超出条目目录"):
                self.reader.load(["ALG-001"])

    def test_inconsistent_id_and_missing_case_hash_fail(self):
        alg_json = (ROOT / "算法条目/ALG-001/ALG-001.json").resolve()
        case_note = (ROOT / "组合案例/CASE-001/CASE-001.md").resolve()
        original_read = reader_module._read_bytes

        def changed(path):
            raw = original_read(path)
            if path == alg_json:
                return raw.replace(b'"ALG-001"', b'"ALG-002"', 1)
            if path == case_note:
                return raw.replace(b"SHA-256", b"SHA-xxx")
            return raw

        with patch.object(reader_module, "_read_bytes", changed):
            for entry_id in ("ALG-001", "CASE-001"):
                with self.subTest(entry_id=entry_id), self.assertRaises(reader_module.LibraryError):
                    self.reader.load([entry_id])

    def test_missing_code_or_source_is_an_error(self):
        original_resolve = Path.resolve
        for relative in ("算法条目/ALG-001/split.py", "算法条目/ALG-001/ALG-001.md"):
            target = ROOT / relative

            def resolve(path, *args, **kwargs):
                if path == target:
                    raise FileNotFoundError(f"missing: {path}")
                return original_resolve(path, *args, **kwargs)

            with self.subTest(path=relative), patch.object(Path, "resolve", resolve):
                with self.assertRaises(reader_module.LibraryError):
                    self.reader.load(["ALG-001"])

    def test_cli_emits_utf8_json_and_errors_have_nonzero_status(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "catalog"],
                                capture_output=True, check=True)
        catalog = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(catalog, self.reader.catalog())
        other_root = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(ROOT), "catalog"],
                                    capture_output=True, check=True)
        self.assertEqual(json.loads(other_root.stdout.decode("utf-8")), catalog)
        selected = subprocess.run([sys.executable, "-B", str(SCRIPT), "load", "ALG-001", "CASE-001"],
                                  capture_output=True, check=True)
        self.assertEqual(json.loads(selected.stdout.decode("utf-8")),
                         self.reader.load(["ALG-001", "CASE-001"]))
        error = subprocess.run([sys.executable, "-B", str(SCRIPT), "load", "ALG-999"],
                               capture_output=True)
        self.assertNotEqual(error.returncode, 0)
        self.assertIn("ALG-999", error.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
