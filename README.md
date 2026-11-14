# 多智能体协作设计混合算法

面向组合优化，协作设计算法组件和组合方式，并根据程序实测结果迭代改进，目标是交付冻结后可独立运行的混合求解器。
正式候选须满足主计划的混合设计合同；单一机制仍可用于工程调试和对照。
本项目从 `roco_paperbanana` 的方案二独立迁入。P0已生成并冻结TSP工程求解程序，尚无运行中的算法设计系统或性能实验。

首版的问题分析者和Retriever只负责初始化，不参与后续迭代。
首版迭代只采用单亲修改和双亲重组，均按“设计者 → 实现者 → 程序评价 → Critic”执行。
预算与停止条件在操作前统一检查，初始化产物保留供后续角色使用。
双亲重组暂以相邻排名配对作为首版起步方案，其相对其他配对方式的优势尚未验证。

## 当前入口

- [主计划](vault/Plan/多智能体协作的通用混合算法自动设计.md)：维护总体设计、P0—P3路线和阶段状态；详细合同见其链接的阶段计划。
- [知识库入库口径与校准样例](vault/Knowledge/P1-只读知识库校准/入库口径与校准说明.md)：按ID阅读样例、核对来源与待确认的数量建议；正式两库尚未建成。
- [P1只读读取器](scripts/p1_library_reader.py)：默认校验并读取冻结的校准快照，列出候选信息或按ID加载说明、代码和来源。
- [两库工作目录](library/working/calibration/)位于项目顶层；[英文校准快照](library/versions/calibration-20261114-03-en/)与[冻结清单](library/manifests/calibration-20261114-03-en/manifest-6e20a83e63570d7f9ae40ddfece9cc86c63e73b5db8078b7a987a562d00f2d26.json)固定33条算法和10条案例，不代表正式库验收。
- [校准样例审阅资料](vault/Knowledge/P1-只读知识库校准/审阅资料入口.md)：查看样例对应的论文全文入口，以及 PaperBanana 本地参考数据的公开副本。
- [P0阶段计划](vault/Plan/P0-TSP最简工程链路.md)：首批TSP实例、求解接口与工程链路任务。
- [P0实例生成器](scripts/generate_p0_tsp.py)：按ReEvo规则生成TSP实例，并核验现有数据快照。
- [P0实例解析与独立评价](scripts/p0_tsp_evaluator.py)：构造求解输入，检查路径并独立计算距离；不运行求解器。
- [P0受限执行入口](scripts/p0_sandbox_exec.py)：按已核验的隔离与资源合同构建和运行单文件程序。
- [P0真实生成与评价](scripts/p0_task4.py)：监督模型调用、受限构建和首批15个实例的独立评价。
- [P0冻结与重跑](scripts/p0_task5.py)：冻结已评价程序并在独立身份下重跑实例。
- [P0作业资源探针](scripts/p0_job_probe.py)：检查无害进程的部分资源限制；不能用于运行候选程序。
- [P0核映射检查](scripts/p0_cpu_topology.py)：核验本机物理核拓扑与实例槽位映射。
- [研究进展摘要](vault/01-Research-Plan-and-Progress.md)。
- [方案二迁入演示PPT](vault/Writing/多智能体协作设计混合算法_方案二.pptx)：保留原演示内容，当前角色与流程以主计划为准。
- [知识索引](vault/02-Index.md)。

当前材料可直接阅读，不要求配置Python、Java或商业求解器。
首批先用TSP走通工程，以CVRP开展性能研究，后续扩展按实测成本决定。
模型生成和资料准备可按需联网；生成后的TSP求解程序使用预先准备的本地实例和依赖，运行时不访问网络。
P0工程链路已通过：真实生成、独立评价和冻结后重跑均完成，15个实例通过验解；原始记录见[P0阶段计划](vault/Plan/P0-TSP最简工程链路.md)。历史部分探针的CPU消耗未采集，P0总实耗无法完整核算。基线版本等后续事项见主计划第六节。

在项目根目录使用 Python 3.13 查看全部候选或加载指定条目：

```powershell
python -B scripts/p1_library_reader.py catalog
python -B scripts/p1_library_reader.py load ALG-001 CASE-001
```

读取器默认使用冻结的校准快照；整理当前草稿时可在子命令前加 `--draft`。正式检索的快照管理、Retriever 全文分析和预算检查尚未接入。字段、校验规则和材料使用限制见[入库口径与校准说明](vault/Knowledge/P1-只读知识库校准/入库口径与校准说明.md#读取器使用)。

## 来源与历史

- [本会话历史](vault/History/会话历史.md)。
- [来源与迁移核验](vault/Knowledge/Source-Provenance.md)。

