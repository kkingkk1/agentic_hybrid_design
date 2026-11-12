# 校准样例的论文资料

本目录收录供审阅 ALG-001 至 ALG-009 及两个案例使用的论文 PDF 和 MinerU 解析资料。ALG-010 至 ALG-033 的其他来源见各自条目的来源记录，本目录未集中复制这些材料。论文资料与本项目的算法库和案例库分开。PDF 保持原样；解析文本可能存在识别错误。

## Split

- 文件：[split_vidal_arxiv_v3.pdf](split_vidal_arxiv_v3.pdf)，用于 ALG-001。
- Thibaut Vidal, *Technical Note: Split Algorithm in O(n) for the Capacitated Vehicle Routing Problem*，*Computers & Operations Research*, 69, 40–47, 2016。正式发表 DOI：[10.1016/j.cor.2015.11.012](https://doi.org/10.1016/j.cor.2015.11.012)。
- 本副本为 [arXiv:1508.02759v3](https://arxiv.org/abs/1508.02759v3) 作者稿，修订日期为 2018-05-05。该稿正文注明 [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)；须署名、仅用于非商业目的，且不得分发改编版本。
- PDF SHA-256：`27b4e55275f7176ff97c1c5c8ccce1b6b5511f1633b1865ebb7b05512eaa9d8a`。

## 2-Opt

- 文件：[two_opt_brodowsky_hougardy_stacs_2021.pdf](two_opt_brodowsky_hougardy_stacs_2021.pdf)，用于 ALG-005 的补充核查。
- [便于网页工具读取的文字版](two_opt_brodowsky_hougardy_stacs_2021.txt)由上述 PDF 提取。转换可能影响公式、图和版式；精确内容以原始 PDF 为准。
- Ulrich A. Brodowsky 和 Stefan Hougardy, *The Approximation Ratio of the 2-Opt Heuristic for the Euclidean Traveling Salesman Problem*，STACS 2021，LIPIcs 187，18:1–18:15。[发表版本及 DOI](https://doi.org/10.4230/LIPIcs.STACS.2021.18)。
- 此 PDF 为 2021-03-10 的会议发表版，采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。ALG-005 当初核对的是 [arXiv 作者稿 v3](https://arxiv.org/abs/2010.02583v3)，不能将本目录的发表版误称为该作者稿。
- PDF SHA-256：`5a40968dd9cae72476cdf71cb83f8f4cc2ea25e8456fb2346dcf0510d83ec5d5`。

## HGS-CVRP

- [MinerU 解析全文](HGS_MinerU/full.md)及同目录的结构化 JSON 和图片来自 Thibaut Vidal 的 [arXiv:2012.10384v2 作者稿](https://arxiv.org/abs/2012.10384v2)，用于 ALG-002、ALG-006 和 CASE-001。原稿 PDF 为 24 页；解析资料含 17 张图片。
- 研究者于 2026-11-08 确认已取得将该作者稿全文及其 MinerU 解析文本公开发布的权利人授权。该确认不代表向其他使用者另行授予许可。
- MinerU 对公式、表格和图片的识别可能有误，关键内容须与作者稿核对。

## ALNS

- [2006 年期刊发表版的 MinerU 解析全文](ALNS_2006_MinerU/full.md)及同目录的结构化 JSON 和 51 个图片文件，用于 ALG-003、ALG-004、ALG-007 至 ALG-009 和 CASE-002。原始 PDF 共 18 页，来自学校提供访问的 JSTOR 期刊数据库。
- Stefan Ropke 和 David Pisinger, *An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows*，*Transportation Science*, 40(4), 455–472, 2006。[正式发表 DOI](https://doi.org/10.1287/trsc.1050.0135)。
- 研究者于 2026-11-09 确认已取得将此发表版的 MinerU 全文公开发布的权利人授权。该确认不代表向其他使用者另行授予许可。
- ALG-003、ALG-004 和 CASE-002 最初核查的是 2005 年作者稿；本目录解析的是 2006 年发表版，两者须区分。MinerU 可能误识别公式、表格或图，关键内容须与原文核对。

GitHub 的原始 PDF 下载链接可能返回 `application/octet-stream`，部分网页工具不能直接解析。遇到此限制时，可使用 Split 的[作者稿 HTML](https://arxiv.org/html/1508.02759v3)，以及上面的 2-Opt 文字版或[出版方 PDF](https://drops.dagstuhl.de/storage/00lipics/lipics-vol187-stacs2021/LIPIcs.STACS.2021.18/LIPIcs.STACS.2021.18.pdf)。
