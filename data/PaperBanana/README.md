# PaperBananaBench 参考资料

这是供项目条目设计审阅使用的 PaperBananaBench 参考集副本，不是本项目的算法库、案例库或测试集。数据来自作者发布的 [PaperBananaBench](https://huggingface.co/datasets/dwzhu/PaperBananaBench)，原始代码与数据获取说明见 [PaperBanana](https://github.com/dwzhu-pku/PaperBanana)。

## 内容

- `diagram`：298 条参考记录、298 张对应图片。
- `plot`：240 条参考记录、240 张对应图片。
- 两个 `ref.json` 均与本机下载的原始压缩包逐字节一致；图片保留参考记录中的相对路径。没有收录 `test.json` 或测试集图片。
- 每个目录的 `ref_parts/` 将 `ref.json` 按原顺序拆分为较小的 JSON 数组，供网页工具分段读取。分卷不改变记录字段和值；需要精确原始格式时读取 `ref.json`。
- 本机原始 `PaperBananaBench.zip` 的 SHA-256 为 `a980d23954c0cb47017cdaa8a9029dbea3598791fd269a457482033821927e37`；压缩包未放入本仓库。

## 读取入口

### 方法图参考集

[完整 diagram/ref.json](diagram/ref.json)；分卷如下，每卷最多 15 条：

[01](diagram/ref_parts/part-001.json) · [02](diagram/ref_parts/part-002.json) · [03](diagram/ref_parts/part-003.json) · [04](diagram/ref_parts/part-004.json) · [05](diagram/ref_parts/part-005.json) · [06](diagram/ref_parts/part-006.json) · [07](diagram/ref_parts/part-007.json) · [08](diagram/ref_parts/part-008.json) · [09](diagram/ref_parts/part-009.json) · [10](diagram/ref_parts/part-010.json)

[11](diagram/ref_parts/part-011.json) · [12](diagram/ref_parts/part-012.json) · [13](diagram/ref_parts/part-013.json) · [14](diagram/ref_parts/part-014.json) · [15](diagram/ref_parts/part-015.json) · [16](diagram/ref_parts/part-016.json) · [17](diagram/ref_parts/part-017.json) · [18](diagram/ref_parts/part-018.json) · [19](diagram/ref_parts/part-019.json) · [20](diagram/ref_parts/part-020.json)

示例：`ref_1` 位于[第一卷](diagram/ref_parts/part-001.json)，其[参考图](diagram/images/%24epsilon%24-Seg%20Sparsely%20Supervised%20Semantic%20Segmentation%20of%20%20Microscopy%20Data_diagram.jpg)位于 `diagram/images/`。

### 统计图参考集

[完整 plot/ref.json](plot/ref.json)；分卷如下，每卷最多 30 条：

[01](plot/ref_parts/part-001.json) · [02](plot/ref_parts/part-002.json) · [03](plot/ref_parts/part-003.json) · [04](plot/ref_parts/part-004.json) · [05](plot/ref_parts/part-005.json) · [06](plot/ref_parts/part-006.json) · [07](plot/ref_parts/part-007.json) · [08](plot/ref_parts/part-008.json)

示例：`ref_0` 位于[第一卷](plot/ref_parts/part-001.json)，对应[参考图](plot/images/multidiff_74.jpg)。

记录中的 `path_to_gt_image` 相对于相应的 `diagram/` 或 `plot/` 目录，而不是相对于 `ref_parts/`。`diagram` 的 `content` 包含论文方法部分文本，`visual_intent` 包含图的说明；`plot` 的字段含义有所不同，具体应以记录及上游说明为准。

## 已知边界与来源

- 图和文本来自上游参考集。上游说明图文版权归原作者；数据集标注 Apache-2.0。请保留来源、作者和[许可文本](LICENSE)，并遵守各原始材料适用的条件。
- 压缩包中的 `diagram` 参考图有三个文件名编码问题，对应 `ref_71`、`ref_284` 和 `ref_309`。本机已有可由 JSON 路径找到的同内容图片；这三张图的字节内容已与压缩包内图片核对。
- 原始 `diagram/ref.json` 中 `ref_1` 的 `split` 值为 `re f`；`ref_260` 和 `ref_305` 的 `content` 为空。本副本保留原样，不将其解释为项目新增错误。
- 参考图对应的论文 PDF 不在本机这份参考集中，也未收入本仓库。上游另有 [PaperBananaDiagramPDFs](https://huggingface.co/datasets/dwzhu/PaperBananaDiagramPDFs)；使用前应检查各论文的条件。
- 分卷只是降低单次读取量。审阅者应说明实际读取了哪些分卷和图片，不应因文件存在就声称逐条读完。

PaperBananaBench 由 Dawei Zhu、Rui Meng、Yale Song、Xiyu Wei、Sujian Li、Tomas Pfister 和 Jinsung Yoon 等发布；引用信息见[数据集页面](https://huggingface.co/datasets/dwzhu/PaperBananaBench)。
