"""发现各新算法目录中随条目保存的检查。"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "library/working/calibration/algorithms"
for number in range(10, 34):
    source = ROOT / f"ALG-{number:03d}" / "check.py"
    spec = importlib.util.spec_from_file_location(f"p1_alg_{number:03d}_checks", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    globals()[f"ALG_{number:03d}_Checks"] = module.Checks
