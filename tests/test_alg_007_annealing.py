"""将条目内的模拟退火检查接入 unittest 发现。"""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "library/working/calibration/algorithms/ALG-007/check_annealing_acceptance.py"
SPEC = importlib.util.spec_from_file_location("alg_007_annealing_checks", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AnnealingTests = MODULE.AnnealingTests
