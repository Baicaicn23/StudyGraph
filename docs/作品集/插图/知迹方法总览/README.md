# 知迹 · 方法总览插图（论文级 method overview figure）

一张图讲完「知迹是怎么工作的」。参照学术论文里的 **method overview figure** 范式：
奶油纸底 + 四栏子图 + 虚线「放大」连接锥 + 顶部图例 + 微缩 3D 质感元素 + 栏底小标题。

## 产出

| 文件 | 说明 |
| --- | --- |
| `知迹-方法总览.svg` | **可编辑源文件**（纯 SVG 矢量，38 KB，无外部依赖） |
| `知迹-方法总览.png` | 3200×1520（1600×760 @2×）高清交付件 |
| `../../scripts/make_overview_figure.py` | 生成器脚本（改文案/配色后重跑即可） |

## 重新生成

```bash
uv run python scripts/make_overview_figure.py --png        # SVG + PNG
uv run python scripts/make_overview_figure.py --png --scale 3   # 更高倍率
```

依赖：仅本机 Chrome（`--headless=new --no-sandbox`）做 SVG→PNG 栅格化。
**这一类图不用生图模型** —— 方法论图要的是**结构精确 + 数字准确**，生图模型两者都做不到。
（**氛围插画是可以用生图模型的**，豆包 Seedream 4.0 的中文渲染准确率约 98%，标题能直接写进图里；
但**数字永远不要交给模型**，错一位就是编造数据。）

## 叙事主线（四栏递进）

```
① 一次回合  ──放大──▶  ② 四路检索  ──放大──▶  ③ 执行治理  ──▶  ④ 撤掉治理会怎样
   怎么走            资料怎么变成能召回的片段    模型能说 ≠ 能跑      代价是什么
```

| 栏 | 讲什么 | 对应背景（产品的三件事） |
| --- | --- | --- |
| ① 回合 | 提问 → 意图路由 → 规划 → 模型⇄工具 → 回答带页码 | 整理资料（引用到第几页） |
| ② 检索 | 入库切块 → 四路并行召回 → 加权 RRF → 词面精排 → top-k | 整理资料 + 结合知识库复习 |
| ③ 治理 | schema 层 + 执行层双权限、写入先确认、护栏/预算/trace | 支撑三件事的工程手段 |
| ④ 对照 | 撤掉治理层的三个具体后果（整栏灰化） | 诚实边界 |

## 设计范式要点（可复用到后续每一页插图）

1. **纸感底 + 圆角面板底衬**：每栏一块极淡的 `#FFFDF7` 圆角矩形，栏间用虚线分隔。
2. **「放大」连接锥**：同一结构的不同尺度用两条虚线 + 端点圆圈连起来，替代箭头，学术味立刻出来。
3. **一栏一个证据形态**：①流程图 ②漏斗+条形 ③分层块+九宫格 ④对照表——绝不混排。
4. **微缩 3D 质感**（不喧宾夺主）：渐变球表示状态、梯形倒角块表示模块、渐变方块贴图表示数据分布。
5. **数字带口径**：检索权重直接标在条形右侧（1.0 / 0.5 / 0.8 / 1.0），命中相似度标在片段条上。
6. **术语双写**：专业词后面跟一句中文（「加权 RRF · k=60，扩写路降权」）。
7. **栏底小标题**：像论文图的 `MPT / LANO / PhLP…`，这里是「① 一次回合 / ② 四路检索 …」。
8. **整栏灰化做对照**：第 ④ 栏所有色换成灰调，视觉上一眼看出这是「撤掉之后」。

## 内容来源（全部可回溯）

| 图中内容 | 代码证据 |
| --- | --- |
| 状态图 route→plan→agent⇄tools | `application/graph.py` `build_graph` |
| 四路召回 + 权重 1.0/0.5/0.8/1.0 | `infrastructure/knowledge.py:643` `weights = [1.0, expansion_weight, 0.8, 1.0]` |
| 加权 RRF k=60 → 词面精排 | `domain/retrieval.py` `rrf_fuse` / `rerank_hits` |
| 双层权限 | `application/routing.py:294` `is_tool_allowed` |
| 写操作先确认 | `application/tools.py` `save_note` 用 `interrupt()` |
| 九个工具 | `application/tools.py`（knowledge_search / mistake_search / save_note / read_file / write_file / list_files / web_search / fetch_url / calculator） |
| 护栏 / 预算 / trace | `domain/guardrails.py`、`infrastructure/usage_repository.py`、`application/trace.py` |
| 逐页切块 + 2048 维向量 | `infrastructure/extract.py`、`infrastructure/embeddings.py`（智谱 embedding-3） |

> ⚠️ 图中「命中片段 P12 / P07 / P31」与相似度 0.91 / 0.84 / 0.78 是**示意数值**，
> 用于说明排序结构；真实评测数字见 `docs/作品集/参赛/03-评测证据包.md`（检索 35 题 Hit@3=MRR=0.9714）。
