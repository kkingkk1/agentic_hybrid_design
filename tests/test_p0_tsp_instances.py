"""核验 P0 实例生成结果和文件保护。"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.generate_p0_tsp import PROJECT, generate


DATA_DIR = PROJECT / "data" / "p0_tsp"
SCRIPT = PROJECT / "scripts" / "generate_p0_tsp.py"


class GenerateP0TspTests(unittest.TestCase):
    def test_matches_frozen_public_reference(self):
        manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        datasets = {entry["shape"][1]: entry for entry in manifest["datasets"]}
        self.assertEqual(set(datasets), {50, 200})
        for size, entry in datasets.items():
            with self.subTest(size=size):
                data = generate(size)
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                self.assertEqual(data, (DATA_DIR / entry["file"]).read_bytes())

    def test_cli_verifies_both_datasets(self):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--verify"], capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_cli_does_not_overwrite_existing_snapshot(self):
        path = DATA_DIR / "train50.json"
        before = path.read_bytes()
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--size", "50", "--output", str(path)],
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("输出文件已存在，未覆盖", result.stderr.decode("utf-8"))
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
