"""将条目内的高代价移除检查接入 unittest 发现。"""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "vault/Knowledge/P1-只读知识库校准/算法条目/ALG-009/check_worst_removal.py"
SPEC = importlib.util.spec_from_file_location("alg_009_worst_checks", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
WorstTests = MODULE.WorstTests
