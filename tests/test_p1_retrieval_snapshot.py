"""验证同一轮检索的版本固定、实际材料记录与停止条件。"""

import hashlib
import shutil
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import p1_library_reader as library


class RetrievalSnapshotTest(unittest.TestCase):
    def test_relative_snapshot_survives_working_directory_change(self):
        events = []
        with chdir(library.PROJECT_ROOT):
            snapshot = library.RetrievalSnapshot(
                library.FORMAL_ROOT.relative_to(library.PROJECT_ROOT),
                manifest=library.FORMAL_MANIFEST.relative_to(library.PROJECT_ROOT),
                record=events.append,
            )
            catalog = snapshot.catalog()

        with TemporaryDirectory() as temp_dir, chdir(temp_dir):
            working = Path("library/working/p1-v1/algorithms/ALG-061")
            working.mkdir(parents=True)
            (working / "ALG-061.json").write_text("draft edit", encoding="utf-8")
            records = snapshot.load(["CASE-001", "ALG-061"])

        plain = library.LibraryReader(library.FORMAL_ROOT, manifest=library.FORMAL_MANIFEST)
        self.assertEqual(catalog, plain.catalog())
        self.assertEqual((len(catalog["algorithms"]), len(catalog["cases"])), (65, 35))
        self.assertEqual(records, plain.load(["CASE-001", "ALG-061"]))
        self.assertEqual([event["operation"] for event in events], ["pin", "catalog", "load"])
        manifest_sha256 = hashlib.sha256(library.FORMAL_MANIFEST.read_bytes()).hexdigest()
        for event in events:
            self.assertEqual(event["snapshot_id"], "p1-v1-20261118-01")
            self.assertEqual(event["manifest_sha256"], manifest_sha256)
            self.assertEqual(event["status"], "ok")
        self.assertEqual(len(events[1]["files"]), 100)
        self.assertTrue(all(path.endswith(".json") for path in events[1]["files"]))
        self.assertEqual(events[2]["ids"], ["CASE-001", "ALG-061"])
        self.assertTrue({
            "cases/CASE-001/CASE-001.json", "cases/CASE-001/CASE-001.md",
            "cases/CASE-001/Program/Genetic.cpp", "algorithms/ALG-001/hgs_split/Split.cpp",
            "algorithms/ALG-061/ALG-061.md",
        }.issubset(events[2]["files"]))
        self.assertNotIn("algorithms/ALG-001/ALG-001.md", events[2]["files"])
        for relative, digest in events[2]["files"].items():
            self.assertEqual(digest, hashlib.sha256((library.FORMAL_ROOT / relative).read_bytes()).hexdigest())

    def test_changed_snapshot_stops_attempt_and_replacement_starts_with_catalog(self):
        events = []
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "frozen"
            shutil.copytree(library.FORMAL_ROOT, root)
            snapshot = library.RetrievalSnapshot(root, record=events.append)
            snapshot.catalog()
            relative = "algorithms/ALG-001/hgs_split/Split.cpp"
            changed = root / relative
            original = changed.read_bytes()
            changed.write_bytes(original + b"\n")

            with self.assertRaisesRegex(library.LibraryError, relative):
                snapshot.load(["ALG-061"])
            self.assertEqual(events[-1]["operation"], "load")
            self.assertEqual(events[-1]["status"], "error")
            self.assertEqual(events[-1]["ids"], ["ALG-061"])
            self.assertIn(relative, events[-1]["reason"])
            self.assertNotIn("files", events[-1])
            changed.write_bytes(original)
            for read in (snapshot.catalog, lambda: snapshot.load(["ALG-061"])):
                with self.assertRaisesRegex(library.LibraryError, "本轮检索已停止"):
                    read()

        replacement = library.RetrievalSnapshot(
            library.DEFAULT_ROOT, manifest=library.DEFAULT_MANIFEST, record=events.append,
        )
        with self.assertRaisesRegex(library.LibraryError, "须先读取候选"):
            replacement.load(["ALG-001"])
        replacement.catalog()
        self.assertEqual(replacement.load(["ALG-001"])[0]["entry"]["algorithm_id"], "ALG-001")
        self.assertNotEqual(events[-1]["manifest_sha256"], events[0]["manifest_sha256"])

    def test_missing_manifest_is_recorded_at_load_and_pin(self):
        events = []
        with TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / library.FORMAL_MANIFEST.name
            shutil.copyfile(library.FORMAL_MANIFEST, manifest)
            snapshot = library.RetrievalSnapshot(manifest=manifest, record=events.append)
            snapshot.catalog()
            manifest.rename(manifest.with_suffix(".unavailable"))
            with self.assertRaisesRegex(library.LibraryError, "无法读取"):
                snapshot.load(["CASE-001"])
            self.assertEqual(events[-1]["snapshot_id"], events[0]["snapshot_id"])
            self.assertEqual(events[-1]["status"], "error")
            self.assertIn(manifest.name, events[-1]["reason"])

            with self.assertRaisesRegex(library.LibraryError, "无法固定两库快照"):
                library.RetrievalSnapshot(manifest=manifest, record=events.append)
            self.assertEqual(events[-1]["operation"], "pin")
            self.assertEqual(events[-1]["status"], "error")

    def test_reads_recheck_the_bytes_used_after_snapshot_verification(self):
        events = []
        snapshot = library.RetrievalSnapshot(record=events.append)
        snapshot.catalog()
        target = library.FORMAL_ROOT / "cases/CASE-001/CASE-001.md"
        read_bytes = library._read_bytes
        reads = 0

        def edit_between_reads(path):
            nonlocal reads
            raw = read_bytes(path)
            if path == target:
                reads += 1
                if reads == 2:
                    return raw + b"\n"
            return raw

        with patch.object(library, "_read_bytes", edit_between_reads):
            with self.assertRaisesRegex(library.LibraryError, "cases/CASE-001/CASE-001.md"):
                snapshot.load(["CASE-001"])
        self.assertEqual(reads, 2)
        self.assertEqual(events[-1]["status"], "error")


if __name__ == "__main__":
    unittest.main()
