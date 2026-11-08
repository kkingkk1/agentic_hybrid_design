# CASE-002：PDPTW 的自适应移除、插入与模拟退火

**摘要：** 在带时间窗的取送货问题中组合多种请求移除、插入启发式和模拟退火；依据搜索反馈调整算子选择权重。

**问题结构：** 每个运输请求有取货和送货位置；被服务请求须由同一车辆先取后送，并满足容量与时间窗。源文允许未安排请求留在 request bank，目标对行驶距离、车辆工作时间和未安排请求数量加权；这与必须服务全部客户的标准 CVRP 不同。

**组件分工与连接：**

1. 从当前路线和 request bank 出发，按权重分别选择一个移除算子和一个插入算子；移除与插入的选择相互独立。
2. 移除算子从当前路线中移出若干请求，形成部分路线及待安排请求；插入算子例如 [Regret-k](../算法条目/ALG-004.md) 尝试重新安排请求，无法插入的请求保留在 request bank。
3. 依据目标值和模拟退火接受准则，决定是否把所得方案作为下一轮当前解；同时维护搜索中找到的最好解。温度逐轮下降，搜索在指定迭代次数后停止。
4. 本轮结果反馈给 [自适应选择机制](../算法条目/ALG-003.md)：记录所用算子的表现和调用次数，每个搜索段结束后更新下一段权重。

**信息交换：** 当前路线与请求集合传给移除算子；部分路线及待安排请求传给插入算子；候选目标值传给接受准则；接受结果和历史最好值转化为算子评分，影响后续选择。

**适用条件与限制：** 原文处理的是带取送配对、时间窗及 request bank 的问题；移植到 CVRP 时需重定义客户插入、可行性、目标和未安排客户处理，不能沿用原问题的可行性判定。接受较差解是搜索选择，不能改变交付解必须满足的任务合同。

**同源独立价值：** 此案例记录移除、插入、接受及反馈之间的完整关系；ALG-003 解释控制机制，ALG-004 解释单个插入算子。三条来自同一篇作者稿，具有不同检索用途。

**出处：** Stefan Røpke、David Pisinger, *An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows*，2006；[作者上传的 2005 年稿全文](https://www.researchgate.net/publication/220413334_An_Adaptive_Large_Neighborhood_Search_Heuristic_for_the_Pickup_and_Delivery_Problem_with_Time_Windows)，第 1—3.5 节；[DTU 文献记录及正式发表 DOI](https://orbit.dtu.dk/en/publications/an-adaptive-large-neighborhood-search-heuristic-for-the-pickup-an/)。2026-11-07 核对作者稿正文；未复制或运行源码。
