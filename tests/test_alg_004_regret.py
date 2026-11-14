"""将 ALG-004 同目录的检查接入项目测试发现。"""

import importlib.util
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "library/working/calibration/algorithms/ALG-004/check_regret_k.py"
)
SPEC = importlib.util.spec_from_file_location("alg_004_regret_checks", SOURCE)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)
RegretKTests = CHECKS.RegretKTests
