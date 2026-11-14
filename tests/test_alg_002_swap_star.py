"""将 ALG-002 同目录的检查接入项目测试发现。"""

import importlib.util
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "library/working/calibration/algorithms/ALG-002/check_swap_star.py"
)
SPEC = importlib.util.spec_from_file_location("alg_002_swap_checks", SOURCE)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)
SwapStarTests = CHECKS.SwapStarTests
