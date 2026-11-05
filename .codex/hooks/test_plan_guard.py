"""历史测试入口：运行用户级 planning-with-files 的跨项目回归用例。"""

import os
import runpy
from pathlib import Path


def main():
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    target = codex_home / "skills/planning-with-files/scripts/test_plan_guard.py"
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
