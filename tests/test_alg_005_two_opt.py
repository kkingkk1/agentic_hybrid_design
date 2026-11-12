"""将 ALG-005 同目录的检查接入项目测试发现。"""

import importlib.util
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "vault/Knowledge/P1-只读知识库校准/算法条目/ALG-005/check_two_opt.py"
)
SPEC = importlib.util.spec_from_file_location("alg_005_two_opt_checks", SOURCE)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)
TwoOptTests = CHECKS.TwoOptTests
