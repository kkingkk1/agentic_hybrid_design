"""将 ALG-003 同目录的检查接入项目测试发现。"""

import importlib.util
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "library/working/calibration/algorithms/ALG-003/check_adaptive_operators.py"
)
SPEC = importlib.util.spec_from_file_location("alg_003_adaptive_checks", SOURCE)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)
AdaptiveOperatorTests = CHECKS.AdaptiveOperatorTests
