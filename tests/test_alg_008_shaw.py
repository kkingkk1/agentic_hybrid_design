"""将条目内的 Shaw 移除检查接入 unittest 发现。"""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "vault/Knowledge/P1-只读知识库校准/算法条目/ALG-008/check_shaw_removal.py"
SPEC = importlib.util.spec_from_file_location("alg_008_shaw_checks", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ShawTests = MODULE.ShawTests
