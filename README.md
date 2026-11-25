# 多智能体协作设计混合算法

面向组合优化，协作设计算法组件和组合方式，并根据程序实测结果迭代改进，目标是交付冻结后可独立运行的混合求解器。
正式候选须满足主计划的混合设计合同；单一机制仍可用于工程调试和对照。
本项目从 `roco_paperbanana` 的方案二独立迁入。P0已生成并冻结TSP工程求解程序，尚无运行中的算法设计系统或性能实验。
项目自研系统、执行评价程序和生成的求解器使用Python；静态库参考代码和外部基线保留原实现语言。

首版的问题分析者和Retriever只负责初始化，不参与后续迭代。
首版迭代只采用单亲修改和双亲重组，均按“设计者 → 实现者 → 程序评价 → Critic”执行。
预算与停止条件在操作前统一检查，初始化产物保留供后续角色使用。
双亲重组暂以相邻排名配对作为首版起步方案，其相对其他配对方式的优势尚未验证。

## 当前入口

- [主计划](vault/Plan/多智能体协作的通用混合算法自动设计.md)：维护总体设计、P0—P3路线和阶段状态；详细合同见其链接的阶段计划。
- P1 正式首版包含65条算法和35条案例。[正式快照](library/versions/p1-v1-20261118-01/) · [冻结清单](library/manifests/p1-v1-20261118-01/manifest-960b1399bb1ff65b51d8817d9b701e7e733bffd0fb865750c57f61ab5448a5e5.json)
- [入库口径与校准记录](vault/Knowledge/P1-只读知识库校准/入库口径与校准说明.md)包含正式首版的覆盖、验证和沿用记录。
- [P1只读读取器](scripts/p1_library_reader.py)在固定快照内列出候选，按ID加载说明、代码与来源。
- [P1 问题分析者](scripts/p1_problem_analyzer.py)提供可独立调用的 `analyze_problem()`，按原问题合同校验并交付 `problem_analysis`。与 Retriever 的接口已用假模型验收。
- [Retriever 初选](scripts/p1_retriever.py)使用英文提示词从两库完整目录选择候选，交付校验后的 ID 和理由。
- [Retriever 全文与补读](scripts/p1_full_retrieval.py)从同一快照读取初选及补读材料，预检完整请求并核对引用与支撑结论。
- [P1 混合方案设计者](scripts/p1_hybrid_designer.py)提供可独立调用的 `design_hybrid()`，接收原问题合同、分析与检索证据，校验后交付结构化设计稿。已用假模型验收。
- [P1 算法实现者](scripts/p1_algorithm_implementer.py)提供可独立调用的 `implement_algorithm()`，按设计版本返回通过静态检查的待评价 Python 源码或可定位的方案缺口。已用假模型验收。
- [P1 初始化串联](scripts/p1_initialization.py)提供 `run_initialization()`，串联分析、检索、设计和实现，支持有限方案修订。正常交付、检索停止与方案回交已用假模型验收。
- [正式工作库](library/working/p1-v1/)供后续修订。[校准工作库](library/working/calibration/)和[校准快照](library/versions/calibration-20261114-03-en/)保留校准样例。
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

## 读取正式库

在项目根目录使用 Python 3.13。显式指定正式快照目录与对应清单，再列出候选或按ID加载。

```powershell
$p1LibraryPath = 'library/versions/p1-v1-20261118-01'
$p1LibraryManifest = 'library/manifests/p1-v1-20261118-01/manifest-960b1399bb1ff65b51d8817d9b701e7e733bffd0fb865750c57f61ab5448a5e5.json'
python -B scripts/p1_library_reader.py --root $p1LibraryPath --manifest $p1LibraryManifest catalog
python -B scripts/p1_library_reader.py --root $p1LibraryPath --manifest $p1LibraryManifest load ALG-061 CASE-037
```

默认参数用于回读校准快照。查看正式工作库时使用 `--root library/working/p1-v1 --draft`。[格式与校验规则](vault/Knowledge/P1-只读知识库校准/入库口径与校准说明.md#读取器使用)

任务 3 接入统一预算账本，并用[初选计划中的 CVRP 样例](vault/Plan/P1-任务2.2-接入Retriever初选.md)进行真实模型试跑。

## 来源与历史

- [本会话历史](vault/History/会话历史.md)。
- [来源与迁移核验](vault/Knowledge/Source-Provenance.md)。

