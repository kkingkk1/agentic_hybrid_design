"""历史入口：转交用户级 planning-with-files，不再维护项目专用检查逻辑。"""

import os
import runpy
from pathlib import Path


def main():
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    target = codex_home / "skills/planning-with-files/scripts/plan_guard.py"
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
