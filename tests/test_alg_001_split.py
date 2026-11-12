"""将 ALG-001 同目录的检查接入项目测试发现。"""

import importlib.util
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "vault/Knowledge/P1-只读知识库校准/算法条目/ALG-001/check_split.py"
)
SPEC = importlib.util.spec_from_file_location("alg_001_split_checks", SOURCE)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)
SplitTests = CHECKS.SplitTests
