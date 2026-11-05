# 计划检查已迁入用户级 skill

通用检查规则与实现由 [planning-with-files](C:/Users/a_wei/.codex/skills/planning-with-files/SKILL.md)
统一维护，适用于不同项目。

- [用户级配置](C:/Users/a_wei/.codex/hooks.json)注册 `UserPromptSubmit` 与 `Stop`。
- [运行与维护说明](C:/Users/a_wei/.codex/skills/planning-with-files/references/plan-guard.md)记录目录识别、检查边界、状态位置、信任与回退方式。
- 本项目 `../hooks.json` 不再注册事件，避免与用户级定义重复运行。
- 本目录两个 Python 文件保留为兼容入口，转交用户级脚本与测试，不含项目专用规则。
- 新状态写入 Codex 用户目录，不再写入本项目 `outputs/codex_plan_guard/`。

原有状态与[2026-10-30 项目试用验收](../../outputs/codex_plan_guard_live_20261030/验收结果.md)
作为历史证据保留。它们不证明迁移后的全局配置已加载。

兼容验证命令：

```powershell
python -I -B .codex/hooks/test_plan_guard.py
```
