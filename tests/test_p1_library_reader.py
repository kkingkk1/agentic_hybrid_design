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
CASE001_CODE_SHA256 = "fea5a9c4913a9eb2a97cd5a1262e0e2b676870e3359ffe20d5a5b70bf5136e4c"
CASE002_CODE_SHA256 = "32ac0efeb603d90972feeb06d3a8055c120ca64812eb80192bdd422c945e9b03"


class LibraryReaderTests(unittest.TestCase):
    def setUp(self):
        # 既有边界测试模拟未冻结草稿；冻结模式另行验证。
        self.reader = reader_module.LibraryReader(ROOT, manifest=None)

    def test_catalog_includes_all_existing_entries_without_code(self):
        catalog = self.reader.catalog()
        for folder, prefix, key, id_key in (
            ("algorithms", "ALG-", "algorithms", "algorithm_id"),
            ("cases", "CASE-", "cases", "case_id"),
        ):
            directories = sorted(p for p in (ROOT / folder).iterdir()
                                 if p.is_dir() and p.name.startswith(prefix))
            self.assertTrue(directories)
            self.assertEqual([x[id_key] for x in catalog[key]], [p.name for p in directories])
            for candidate, directory in zip(catalog[key], directories):
                original = json.loads((directory / f"{directory.name}.json").read_bytes())
                self.assertNotIn("code", candidate)
                if key == "algorithms":
                    self.assertNotIn("function", original)
                    self.assertNotIn("function", candidate)
                    for field in ("category", "summary"):
                        self.assertEqual(candidate[field], original[field])
                else:
                    self.assertEqual(candidate["description"], "".join(original["description"]))

    def test_selected_entries_return_full_material_in_requested_order(self):
        case, algorithm = self.reader.load(["CASE-001", "ALG-001"])
        case_dir = ROOT / "cases" / "CASE-001"
        alg_dir = ROOT / "algorithms" / "ALG-001"
        case_raw = (case_dir / "CASE-001.json").read_bytes()
        case_original = json.loads(case_raw)
        self.assertEqual(case["entry"]["case_id"], "CASE-001")
        self.assertEqual(case["entry"]["description"], "".join(case_original["description"]))
        self.assertEqual(hashlib.sha256(case["entry"]["code"].encode("utf-8")).hexdigest(),
                         CASE001_CODE_SHA256)
        self.assertTrue(all(isinstance(item, dict) for item in case_original["code"]))
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

    def test_alg001_author_source_matches_complete_case(self):
        case, algorithm = self.reader.load(["CASE-001", "ALG-001"])
        case_dir = ROOT / "cases/CASE-001"
        manifest = json.loads((case_dir / "CASE-001.json").read_bytes())["code"]
        shared = [item for item in manifest if item.get("algorithm_id") == "ALG-001"]
        self.assertEqual(len(shared), 8)
        self.assertEqual(len(manifest) - len(shared), 9)
        for item in shared:
            self.assertFalse((case_dir / item["name"]).exists())
        lines = case["entry"]["code"].split("\n")
        files = algorithm["entry"]["code"]["files"]
        self.assertEqual(algorithm["entry"]["code"]["entry"], "Split::generalSplit")
        self.assertEqual(
            {Path(item["path"]).name for item in files},
            {"Split.cpp", "Split.h", "Params.cpp", "Params.h", "Individual.cpp",
             "Individual.h", "CircleSector.h", "LICENSE"},
        )
        for item in files:
            name = Path(item["path"]).name
            source_name = name if name == "LICENSE" else f"Program/{name}"
            marker = f"// --- FILE: {source_name} ---"
            self.assertEqual(lines.count(marker), 1)
            start = lines.index(marker) + 1
            end = next((i for i in range(start, len(lines))
                        if lines[i].startswith("// --- FILE: ")), len(lines))
            with self.subTest(source=source_name):
                self.assertEqual(item["content"].replace("\r\n", "\n"),
                                 "\n".join(lines[start:end]))

    def test_case_mention_does_not_load_an_unselected_algorithm(self):
        alg6_dir = ROOT / "algorithms/ALG-006"
        alg6_json = (alg6_dir / "ALG-006.json").resolve()
        alg6_code = (alg6_dir / "order_crossover.py").resolve()
        with patch.object(reader_module, "_read_bytes", wraps=reader_module._read_bytes) as reads:
            selected = self.reader.load(["ALG-001", "ALG-002", "CASE-001"])
        self.assertEqual([item["entry"].get("algorithm_id", item["entry"].get("case_id"))
                          for item in selected], ["ALG-001", "ALG-002", "CASE-001"])
        self.assertIn("ALG-006", selected[-1]["entry"]["description"])
        self.assertIn("void Genetic::crossoverOX", selected[-1]["entry"]["code"])
        read_paths = {call.args[0] for call in reads.call_args_list}
        self.assertNotIn(alg6_json, read_paths)
        self.assertNotIn(alg6_code, read_paths)

        supplemental = self.reader.load(["ALG-006"])[0]["entry"]
        self.assertEqual(supplemental["algorithm_id"], "ALG-006")
        self.assertEqual(supplemental["code"]["files"][0]["content"],
                         alg6_code.read_bytes().decode("utf-8"))

    def test_frozen_catalog_rejects_changed_algorithm_and_case_metadata(self):
        frozen = reader_module.LibraryReader(ROOT)
        original_read = reader_module._read_bytes
        for relative in ("algorithms/ALG-010/ALG-010.json", "cases/CASE-010/CASE-010.json"):
            target = (ROOT / relative).resolve()
            doc = json.loads(original_read(target))
            doc["description"] = ["changed description"]
            if relative.startswith("algorithms"):
                doc["summary"] = "changed summary"
            changed_raw = json.dumps(doc, ensure_ascii=False).encode("utf-8")

            def changed(path):
                return changed_raw if path == target else original_read(path)

            with self.subTest(path=relative), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaisesRegex(reader_module.LibraryError, "冻结文件 SHA-256"):
                    frozen.catalog()

    def test_frozen_case_rejects_metadata_even_when_source_hash_is_updated(self):
        frozen = reader_module.LibraryReader(ROOT)
        case_path = (ROOT / "cases/CASE-001/CASE-001.json").resolve()
        note_path = (ROOT / "cases/CASE-001/CASE-001.md").resolve()
        original_read = reader_module._read_bytes
        raw_case = original_read(case_path)
        doc = json.loads(raw_case)
        doc["description"] = ["changed description"]
        changed_case = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        old_hash = hashlib.sha256(raw_case).hexdigest().encode("ascii")
        new_hash = hashlib.sha256(changed_case).hexdigest().encode("ascii")

        def changed(path):
            if path == case_path:
                return changed_case
            raw = original_read(path)
            return raw.replace(old_hash, new_hash) if path == note_path else raw

        with patch.object(reader_module, "_read_bytes", changed):
            with self.assertRaisesRegex(reader_module.LibraryError, "冻结文件 SHA-256"):
                frozen.load(["CASE-001"])

    def test_frozen_load_rejects_changed_metadata_source_and_shared_code(self):
        frozen = reader_module.LibraryReader(ROOT)
        original_read = reader_module._read_bytes
        for relative, selected in (
            ("algorithms/ALG-001/ALG-001.json", "ALG-001"),
            ("algorithms/ALG-001/ALG-001.md", "ALG-001"),
            ("algorithms/ALG-001/hgs_split/Split.cpp", "ALG-001"),
            ("cases/CASE-001/CASE-001.md", "CASE-001"),
            ("algorithms/ALG-001/hgs_split/Split.cpp", "CASE-001"),
            ("cases/CASE-001/Program/Genetic.cpp", "CASE-001"),
        ):
            target = (ROOT / relative).resolve()

            def changed(path):
                raw = original_read(path)
                return raw + b"\n" if path == target else raw

            with self.subTest(path=relative, selected=selected), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaisesRegex(reader_module.LibraryError, "冻结文件 SHA-256"):
                    frozen.load([selected])

    def test_frozen_reader_rechecks_manifest_and_entry_set(self):
        frozen = reader_module.LibraryReader(ROOT)
        original_read = reader_module._read_bytes

        def changed_manifest(path):
            raw = original_read(path)
            return raw + b" " if path == frozen.manifest else raw

        with patch.object(reader_module, "_read_bytes", changed_manifest):
            for operation in (frozen.catalog, lambda: frozen.load(["ALG-001"])):
                with self.subTest(operation=operation), self.assertRaisesRegex(
                        reader_module.LibraryError, "冻结清单 SHA-256"):
                    operation()

        original_iterdir = Path.iterdir
        case_base = ROOT / "cases"

        def without_case(path):
            children = list(original_iterdir(path))
            return iter([child for child in children if child.name != "CASE-010"]
                        if path == case_base else children)

        with patch.object(Path, "iterdir", without_case):
            with self.assertRaisesRegex(reader_module.LibraryError, "条目集合与冻结清单不一致"):
                frozen.catalog()

    def test_frozen_snapshot_restores_all_recorded_files(self):
        frozen = reader_module.LibraryReader(ROOT)
        manifest = frozen._manifest()
        self.assertIsNotNone(manifest)
        actual_paths = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*")
                        if path.is_file() and "__pycache__" not in path.parts
                        and path.suffix != ".pyc"}
        self.assertEqual(actual_paths, set(manifest["files"]))
        for relative, expected in manifest["files"].items():
            path = ROOT.joinpath(*relative.split("/"))
            with self.subTest(path=relative):
                raw = path.read_bytes()
                self.assertEqual(len(raw), expected["size"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
        self.assertEqual(len(frozen.load(manifest["entries"])), len(manifest["entries"]))

    def test_english_catalog_and_sources_preserve_all_entries(self):
        frozen = reader_module.LibraryReader()
        catalog = frozen.catalog()
        ids = ([item["algorithm_id"] for item in catalog["algorithms"]]
               + [item["case_id"] for item in catalog["cases"]])
        self.assertEqual((len(catalog["algorithms"]), len(catalog["cases"])), (33, 10))
        for item in frozen.load(ids):
            entry = item["entry"]
            visible = [entry["description"], item["source"]["content"]]
            if "algorithm_id" in entry:
                self.assertNotIn("function", entry)
                visible.extend(entry["category"])
                visible.extend((entry["summary"], entry["code"]["origin"]))
            else:
                visible.append(entry["category"])
            with self.subTest(entry=entry.get("algorithm_id", entry.get("case_id"))):
                for text in visible:
                    self.assertNotRegex(text, r"[\u3400-\u9fff]")

    def test_previous_chinese_snapshot_remains_readable(self):
        root = PROJECT / "library/versions/calibration-20261113-01"
        manifest = (PROJECT / "library/manifests/calibration-20261113-01"
                    / "manifest-12a68128f249ef58fc264e7173652ca3f95b7cff3788578dd7d1442c43c43d5c.json")
        reader = reader_module.LibraryReader(root, manifest=manifest)
        catalog = reader.catalog()
        self.assertEqual((len(catalog["algorithms"]), len(catalog["cases"])), (33, 10))
        self.assertIn("function", catalog["algorithms"][0])
        case = reader.load(["CASE-001"])[0]
        self.assertEqual(hashlib.sha256(case["entry"]["code"].encode("utf-8")).hexdigest(),
                         CASE001_CODE_SHA256)

    def test_previous_english_snapshot_keeps_its_original_catalog(self):
        root = PROJECT / "library/versions/calibration-20261113-02-en"
        manifest = (PROJECT / "library/manifests/calibration-20261113-02-en"
                    / "manifest-a3654379174a37407eec67b1cdc117683d590d026737456f5744c4ca427a5f91.json")
        old = reader_module.LibraryReader(root, manifest=manifest)
        candidate = old.catalog()["algorithms"][0]
        original = json.loads((root / "algorithms/ALG-001/ALG-001.json").read_bytes())
        self.assertEqual(candidate["function"], original["function"])
        self.assertEqual(old.load(["ALG-001"])[0]["entry"]["function"], original["function"])

    def test_new_algorithm_entries_only_drop_the_old_function_field(self):
        old = PROJECT / "library/versions/calibration-20261113-02-en/algorithms"
        for number in range(1, 34):
            entry_id = f"ALG-{number:03d}"
            relative = Path(entry_id) / f"{entry_id}.json"
            before = json.loads((old / relative).read_bytes())
            after = json.loads((ROOT / "algorithms" / relative).read_bytes())
            with self.subTest(entry_id=entry_id):
                self.assertIn("function", before)
                before.pop("function")
                self.assertEqual(after, before)

    def test_mixed_current_and_legacy_entry_directories_are_rejected(self):
        original_exists = Path.exists
        legacy_folder = ROOT / "算法条目"

        def exists(path):
            return True if path == legacy_folder else original_exists(path)

        with patch.object(Path, "exists", exists):
            with self.assertRaisesRegex(reader_module.LibraryError, "不能混用"):
                reader_module.LibraryReader().catalog()

    def test_case002_source_is_unchanged_after_file_migration(self):
        case = self.reader.load(["CASE-002"])[0]
        original = json.loads((ROOT / "cases/CASE-002/CASE-002.json").read_bytes())
        files = original["code"]
        self.assertEqual(len(files), 13)
        self.assertEqual(sum(item["name"].endswith(".py") for item in files), 11)
        self.assertTrue(all(item.get("marker") == "#" for item in files))
        self.assertTrue(all("algorithm_id" not in item for item in files))
        self.assertEqual(hashlib.sha256(case["entry"]["code"].encode("utf-8")).hexdigest(),
                         CASE002_CODE_SHA256)

    def test_all_case_entries_load_their_registered_files(self):
        case_ids = [item["case_id"] for item in self.reader.catalog()["cases"]]
        self.assertTrue({f"CASE-{number:03d}" for number in range(1, 11)} <= set(case_ids))
        for result in self.reader.load(case_ids):
            entry = result["entry"]
            case_id = entry["case_id"]
            manifest_path = ROOT / "cases" / case_id / f"{case_id}.json"
            files = json.loads(manifest_path.read_bytes())["code"]
            with self.subTest(case=case_id):
                self.assertTrue(any(item["name"] == "LICENSE" for item in files))
                for item in files:
                    marker = item.get("marker", "//")
                    self.assertIn(f"{marker} --- FILE: {item['name']} ---\n", entry["code"])

    def test_legacy_case_code_lines_remain_readable(self):
        case_path = (ROOT / "cases/CASE-002/CASE-002.json").resolve()
        source_path = (ROOT / "cases/CASE-002/CASE-002.md").resolve()
        original_read = reader_module._read_bytes
        raw = original_read(case_path)
        old_hash = hashlib.sha256(raw).hexdigest().encode("ascii")
        old_case = json.loads(raw)
        old_case["code"] = ["# legacy file", "print('ok')", ""]
        encoded = json.dumps(old_case, ensure_ascii=False).encode("utf-8")
        new_hash = hashlib.sha256(encoded).hexdigest().encode("ascii")

        def changed(path):
            if path == case_path:
                return encoded
            raw_file = original_read(path)
            return raw_file.replace(old_hash, new_hash) if path == source_path else raw_file

        with patch.object(reader_module, "_read_bytes", changed):
            case = self.reader.load(["CASE-002"])[0]
        self.assertEqual(case["entry"]["code"], "# legacy file\nprint('ok')\n")

    def test_case_rejects_invalid_file_references(self):
        case_path = (ROOT / "cases/CASE-001/CASE-001.json").resolve()
        source_path = (ROOT / "cases/CASE-001/CASE-001.md").resolve()
        original_read = reader_module._read_bytes
        raw_case = original_read(case_path)
        case = json.loads(raw_case)
        old_hash = hashlib.sha256(raw_case).hexdigest().encode("ascii")
        self.assertIn(old_hash, original_read(source_path))
        shared = next(i for i, item in enumerate(case["code"]) if "algorithm_id" in item)
        local = next(i for i, item in enumerate(case["code"]) if "algorithm_id" not in item)

        def invalid_unknown_algorithm(doc):
            doc["code"][shared]["algorithm_id"] = "ALG-999"

        def invalid_algorithm_path(doc):
            doc["code"][shared]["path"] = "check_hgs_split.cpp"

        def invalid_shared_hash(doc):
            doc["code"][shared]["sha256_lf"] = "0" * 64

        def invalid_local_path(doc):
            doc["code"][local]["path"] = "../CASE-001.json"

        def invalid_name(doc):
            doc["code"][local]["name"] = "../outside.cpp"

        def duplicate_name(doc):
            doc["code"][local]["name"] = doc["code"][shared]["name"].upper()

        def invalid_marker(doc):
            doc["code"][local]["marker"] = "\ninvalid"

        for mutate in (invalid_unknown_algorithm, invalid_algorithm_path, invalid_shared_hash,
                       invalid_local_path, invalid_name, duplicate_name, invalid_marker):
            altered = copy.deepcopy(case)
            mutate(altered)
            encoded = json.dumps(altered, ensure_ascii=False).encode("utf-8")
            new_hash = hashlib.sha256(encoded).hexdigest().encode("ascii")

            def changed(path):
                raw = original_read(path)
                if path == case_path:
                    return encoded
                if path == source_path:
                    return raw.replace(old_hash, new_hash)
                return raw

            with self.subTest(mutation=mutate.__name__), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaises(reader_module.LibraryError):
                    self.reader.load(["CASE-001"])

    def test_case_rejects_modified_local_and_shared_code(self):
        original_read = reader_module._read_bytes
        for relative, selected in (("cases/CASE-001/Program/Genetic.cpp", "CASE-001"),
                                   ("algorithms/ALG-001/hgs_split/Split.cpp", "CASE-001"),
                                   ("cases/CASE-002/alns_pdptw/alns.py", "CASE-002")):
            target = (ROOT / relative).resolve()

            def changed(path):
                raw = original_read(path)
                return raw + b"\n" if path == target else raw

            with self.subTest(path=relative), patch.object(reader_module, "_read_bytes", changed):
                with self.assertRaisesRegex(reader_module.LibraryError, "SHA-256"):
                    self.reader.load([selected])

    def test_invalid_unknown_and_duplicate_ids_fail(self):
        for ids in (["../ALG-001"], ["ALG-01"], ["CASE-001/extra"], ["ALG-999"],
                    ["ALG-001", "ALG-001"]):
            with self.subTest(ids=ids), self.assertRaises(reader_module.LibraryError):
                self.reader.load(ids)

    def test_algorithm_code_changes_and_case_json_changes_are_rejected(self):
        for relative, selected in (
            ("algorithms/ALG-001/hgs_split/Split.cpp", "ALG-001"),
            ("cases/CASE-001/CASE-001.json", "CASE-001"),
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
        target = (ROOT / "algorithms/ALG-001/hgs_split/Split.cpp").resolve()
        original_read = reader_module._read_bytes

        def crlf(path):
            raw = original_read(path)
            return raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") if path == target else raw

        with patch.object(reader_module, "_read_bytes", crlf):
            item = self.reader.load(["ALG-001"])[0]["entry"]["code"]["files"][0]
        self.assertIn("\r\n", item["content"])
        self.assertEqual(item["content"], crlf(target).decode("utf-8"))

    def test_code_path_cannot_escape_its_entry(self):
        target = (ROOT / "algorithms/ALG-001/ALG-001.json").resolve()
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
        target = ROOT / "algorithms/ALG-001/hgs_split/Split.cpp"
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            if path == target:
                return original_resolve(PROJECT / "README.md", strict=True)
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            with self.assertRaisesRegex(reader_module.LibraryError, "路径超出条目目录"):
                self.reader.load(["ALG-001"])

    def test_inconsistent_id_and_missing_case_hash_fail(self):
        alg_json = (ROOT / "algorithms/ALG-001/ALG-001.json").resolve()
        case_note = (ROOT / "cases/CASE-001/CASE-001.md").resolve()
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
        for relative in ("algorithms/ALG-001/hgs_split/Split.cpp", "algorithms/ALG-001/ALG-001.md"):
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
        draft = subprocess.run([sys.executable, "-B", str(SCRIPT), "--draft", "catalog"],
                               capture_output=True, check=True)
        draft_reader = reader_module.LibraryReader(reader_module.DRAFT_ROOT, manifest=None)
        self.assertEqual(json.loads(draft.stdout.decode("utf-8")), draft_reader.catalog())
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
