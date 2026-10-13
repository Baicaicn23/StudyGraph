# 知迹

**用 [LangGraph](https://langchain-ai.github.io/langgraph/) 编排的个人学习助理**——把聊天、学科知识库、检索、错题沉淀、出题复习和日程排期，串成一条可以断点续跑的闭环。

知迹 面向大学生：平时把资料分学科存进去、聊天随手沉淀笔记；期末让助手检索资料讲解、从错题和知识库自动出题、按掌握度安排复习。它把 LangGraph 的**状态机、检查点、Human-in-the-Loop 与流式输出**用在真实的学习流程上。

## 核心能力

### 对话与教学

| 能力                  | 说明                                                                                                                                                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🧭 意图路由             | 每条消息先判意图（讲解 / 练习 / 进度 / 检索 / 计算 / 闲聊），路由到对应子智能体                                                                                                                                                                  |
| 🧩 显式状态图            | 一次回合就是一张 LangGraph 状态图：`route → plan → agent ⇄ tools`，循环与分支都写在明面上                                                                                                                                                |
| 🎓 AI 私教人格          | 三条红线：个人数据优先（先检索你的笔记/错题并标出处）、引导优先于告知（苏格拉底式分步提问）、贴合掌握水平（按学科掌握度调整讲解深度）；配套 Markdown 笔记写作规范（固定骨架 + LaTeX + 自测三问）                                                                                                      |
| 🪟 回答过程流            | SSE 推 `step` 事件（理解问题 / 制定计划 / 工具调用 + 参数与结果摘要），**有工具调用时默认展开**，卡片头部带链路摘要（检索知识库 → 整理笔记）；**单行活动模式**（进行中只显示当前动作，完成渐隐、下一行淡入；历史收成「已完成 N 步 · 工具 ×次数」）；回合结束有**收束条**（✓ 已完成 · 用时 · 后续动作）；HITL 中断在消息里可见；中断前后合并落库，历史回放能看到完整过程 |
| 💬 会话系统             | 会话自动保存 + 模型自动起标题；按**课程空间**分组（新对话必选课程，无课程时引导一键创建），**长期记忆按课程隔离**；系统保留隐藏兜底空间「未归类」（接住旧数据与直连 API，防止记忆落进黑洞桶）                                                                                                           |
| 📎 聊天附件             | ＋菜单 / 粘贴（Cmd+V）/ 拖入三条路上传 PDF·Word·PPT·TXT·MD·图片（≤6 个、≤5MB）；PDF/Word/PPT 原样落盘，**图片走视觉转写入库**；图片可点击全屏预览                                                                                                             |
| 🛡️ 工具最小权限          | **双层生效**：schema 层只给模型看允许的工具，执行层再拦一次黑名单；MCP 工具默认关闭，仅私教/检索子智能体可开                                                                                                                                                   |
| ✋ Human-in-the-Loop | 「沉淀进知识库」这类写操作先 `interrupt()` 请求确认；「允许完全访问」开关可一键放行（收在 ＋ 菜单里）                                                                                                                                                      |
| 🧠 长期记忆             | 从对话抽取事实注入提示词（标注"数据而非指令"），按项目隔离                                                                                                                                                                                   |
| 🚧 护栏 Guardrails    | 输入：拦越界 / 提示词注入；输出：拦空回答与系统提示词泄漏                                                                                                                                                                                   |

### 知识库

| 能力               | 说明                                                                                                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 🔎 混合检索 RAG      | SQLite + FTS5 **trigram** 中文检索（jieba 词级查询）+ **向量余弦相似度** + **同义/中英扩写** + **短词 LIKE**，四路用 **RRF 加权融合**（扩写路降权，靠推断的召回不与字面命中平起平坐）；切块按结构来（PDF/PPT 按页、Markdown 按标题、纯文本盲切），结果带出处；接真 Embedding（如智谱 embedding-3）后同义换词也能召回，向量服务故障自动降级纯关键词 |
| ✦ 智能检索           | 检索范围两模式：**✦智能检索**（默认，模型按问题从候选库挑 1-3 个相关库，编造库名过滤、失败回落全库）/ **指定知识库**（手动勾选）；「存进知识库」选库条可**内联新建**并自动选中                                                                        |
| 📥 资料入库          | TXT / Markdown / PDF 抽文本；PDF/Word/PPT/Excel **原样秒传 + 懒解析**（markitdown 引擎，PDF/PPT 逐页切块带页码出处，魔数校验挡损坏文件）；**图片走视觉转写**成规范 Markdown 笔记                                         |
| 🫗 智能沉淀          | 「加入知识库」走模型提炼（按笔记规范去掉对话性内容，无知识内容时诚实 422），Mock 模式回退原文转存                                                                                                                    |
| 🗂️ Obsidian 式阅读 | 笔记页三栏：常驻共享文件树 + 正文 + 右侧双 tab 面板（AI 助手 / 目录大纲），面板**内联折叠展开**、可拖拽调宽，大纲带 scroll-spy                                                                                          |
| 🔧 全量 CRUD       | 知识库 / 资料的新建、编辑（重建切块 + 向量 + FTS 索引）、删除；**右键菜单**（光标处三形态：课程 / 会话 / 空白）+ 悬停操作                                                                                                |

### 学习闭环

| 能力            | 说明                                                                                         |
| ------------- | ------------------------------------------------------------------------------------------ |
| 🎯 错题 → 出题    | 错题带学科；从错题或知识库出题，模型写题失败自动回退模板题                                                              |
| 📈 难度分层       | 三档 basic / apply / transfer（对应"记忆 / 应用 / 迁移"）；`auto` 按该学科掌握度自动分档（<40 基础 / <80 进阶 / ≥80 迁移） |
| 🔁 流式出题反馈     | `POST /api/practice/generate/stream` 每出一题推一帧进度；前端有骨架卡依次点亮的模拟动画 + 真实进度条                     |
| 🃏 牌堆复习       | 一次一题：卡片按开始时间排在牌堆，自评后卡片飞出、下一题顶上；作答区是主工作区（150px 起）                                           |
| ⏱️ 间隔重复 + 掌握度 | 自评 again/hard/good/easy → 下次复习时间 + 掌握度自动更新（幂等可测的纯函数）                                       |
| 🗓️ 今日复习      | 汇总到期题 / 薄弱学科 / 近期误区 + 学习活跃度热力图 + 任务清单                                                      |
| 📅 日程（时间轴）    | 收件箱（未排期的想法）→ 一键排进时间轴；固定 06:00–24:00 刻度、周条密度点、进行中/已完成态、当前时刻指示；**排期是确定性算法**（当天最早空档，零模型调用）    |

### Agent 工程

| 能力                      | 说明                                                                                                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 📊 评测门禁                 | 检索 Hit@K / MRR + 意图准确率，基线 JSON + 容差回归，可直接进 CI                                                                                                                                  |
| 🔍 回合 trace             | 把一次会话读成诊断树，归因到 检索 / 工具 / 模型 层                                                                                                                                                  |
| 🔁 工具可靠性                | 单次超时 + 仅对可重试错误做有限退避重试；失败转成工具消息、不炸整回合                                                                                                                                           |
| 🪟 上下文压缩                | 历史过长时保留最近轮次，更早的压缩成提示（不拆散工具调用对）                                                                                                                                                 |
| 🗺️ 规划 Plan-and-Execute | 复杂请求先出计划再执行；简单请求跳过（省延迟与成本）                                                                                                                                                     |
| 🎚️ 模型路由                | 按意图 / 复杂度选 small / standard / large 档位（可配不同模型）                                                                                                                                 |
| 💰 成本控制                 | token 记账（按次 / 按模型）+ 当日预算，超限阻止真实调用                                                                                                                                              |
| 🌐 联网能力                 | `web_search`：主模型是 DeepSeek 时自动走**原生联网搜索**（服务端搜索+抓网页全文+基于全文整理答案，质量最好的中文路径）；否则博查 / Tavily / 必应+DDG 双引擎依次回落，结果按概念覆盖过滤。`fetch_url` 读网页正文（trafilatura 抽取，SSRF 防护只允许公网地址）；引用注明来源 URL |
| 📁 文件工作区                | `write_file` / `read_file` / `list_files`：学生专属沙箱目录 `data/workspace/<user>/`，路径穿越/绝对路径全拒绝；写不出去沙箱，不做 HITL                                                                        |
| 🔗 MCP 客户端              | 自写 stdio JSON-RPC：启动 server、发现并注册外部工具（前缀 `mcp_`）                                                                                                                               |
| 💾 断点持久化                | `AsyncSqliteSaver` 检查点：会话可续、HITL 可恢复；**检查点也是数据恢复的救命稻草**                                                                                                                        |
| 🌊 流式输出                 | SSE：`token` / `step` / `status` / `session` / `interrupt` / `guard` / `done` / `error`                                                                                         |
| 🤖 双模型适配                | 默认确定性 Mock（零成本），可切任意 OpenAI 兼容平台（已实测 DeepSeek-V4.1-Flash，含视觉转写）                                                                                                                |

## 界面一览

侧栏功能导航共 5 项（其余页面从入口跳转）：

| 导航    | 路由           | 页面                                                                       |
| ----- | ------------ | ------------------------------------------------------------------------ |
| AI 对话 | `/`          | 流式回答 + 过程卡片 + 附件 + Github 式提问热力图；右上角「＋ 新对话」                              |
| 错题练习  | `/practice`  | 一个入口两个 tab：**错题本**（沉淀 + 按错误类型智能分类 + 一键出变式题）· **专项练习**（挑错题 → 流式生成 → 牌堆复习） |
| 今日复习  | `/plan`      | 指标卡 + 活跃度热力图 + 今日任务 + 掌握度 + token 用量                                     |
| 日程    | `/schedule`  | 收件箱 + 06:00–24:00 时间轴（自绘时间/日期选择器）                                        |
| 知识库   | `/knowledge` | 目录树 + 内容 + AI 问答；笔记阅读 `/knowledge/doc/[id]` 三栏 + AI 助手/大纲双 tab           |

> `/mistakes` 保留为重定向（→ `/practice?tab=mistakes`），旧链接不失效。

全局侧栏：上方功能导航，下方**课程空间**（会话按课程分组、默认折叠、可拖宽 180–340px）。

> 全站页面切换有统一过渡：退场淡出上移 → 入场淡入归位（各 200ms ease-out、4px 位移），  
> 侧栏保持静止，首屏与刷新不播，`prefers-reduced-motion` 自动关闭。

## 架构一览

```text
        ┌──────────┐    route       ┌──────────┐
START ─▶│  route   │──────────────▶ │  agent   │◀─┐
        └──────────┘ 意图 + 工具权限  └────┬─────┘  │
                                         │        │
                              有工具调用 │  无工具 │
                                         ▼        │
                                    ┌─────────┐   │
                                    │  tools  │───┘
                                    └─────────┘
                       执行层权限拦截 · HITL interrupt
```

一次回合的数据流、状态模型与设计取舍，见 [docs/架构设计.md](docs/架构设计.md)。

## 分层架构（洋葱 / 六边形）

代码按**依赖只朝内**分层，外部技术可替换而不动业务规则：

| 层                   | 目录                | 允许依赖    | 内容                                                    |
| ------------------- | ----------------- | ------- | ----------------------------------------------------- |
| 领域 Domain           | `domain/`         | 仅标准库    | 间隔重复、掌握度、出题规则、RRF 融合、记忆抽取、笔记风格规范                      |
| 应用 Application      | `application/`    | 领域 + 端口 | 用例编排（学习闭环 / 日程排期 / 会话）、**端口 Protocol**、LangGraph 图与工具 |
| 基础设施 Infrastructure | `infrastructure/` | 应用 / 领域 | SQLite 三个仓储（学习 / 会话 / 日程）、Embedding、LLM、文件解析与视觉转写     |
| 接口 Interfaces       | `interfaces/`     | 全部      | FastAPI、CLI（**组合根**，负责装配）                             |

- 应用层只依赖 `application/ports.py` 里的 **Protocol**（`KnowledgePort` /  
  `LearningRepositoryPort` / `ScheduleRepositoryPort` / `ChatRepositoryPort` /  
  `UsageRepositoryPort` / `EmbeddingPort` / `ChatModelPort`），不 import 任何具体实现——  
  换数据库、换模型、换检索都不用改业务代码。
- 领域层是纯逻辑：测它不用起数据库、不联网。

## 快速开始

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run zhiji "帮我算一下 7 * 9"
```

预期输出：

```text
（模拟模型）根据工具返回的结果：63
```

沉淀一条笔记（写操作会请求确认，`--yes` 自动同意）：

```bash
uv run zhiji "记住：我在准备月底的微积分测验" --yes
uv run zhiji "我的笔记里怎么讲微积分测验的？"
```

### 启动 Web 界面（推荐）

```bash
cd frontend && npm install && cd ..   # 首次
./scripts/dev.sh                       # 后端 8011 + 前端 3000
```

打开 <http://localhost:3000>。前端默认连 `http://127.0.0.1:8011`，可用 `NEXT_PUBLIC_API_BASE` 覆盖。

> **想要有内容可演示**：先播种演示数据（5 个学科知识库、15 份自编复习笔记、3 条典型误区）：
>
> ```bash
> uv run zhiji-demo --reset
> ```
>
> 注意：`--reset` 会**清空并重建**数据库，真在使用前先备份（见下）。

### 数据与备份

| 路径                  | 内容                                                 |
| ------------------- | -------------------------------------------------- |
| `data/zhiji.db`     | 知识库、学习数据、会话、日程、LangGraph 检查点（全部数据都在这个文件里）          |
| `data/attachments/` | 聊天附件里的图片原文件（`/api/chat/attachments/{id}/raw` 提供预览） |
| `data/backups/`     | 手动备份（`sqlite3` 在线备份 API 生成，含 `-wal` 内容，可直接还原）      |

备份与清空（**清空前务必先备份**）：

```bash
# 在线一致性备份（WAL 模式下安全）
uv run python -c "import sqlite3,time;s=sqlite3.connect('data/zhiji.db');d=sqlite3.connect(f'data/backups/zhiji-{time.strftime(\"%Y%m%d-%H%M%S\")}.db');s.backup(d);d.close();s.close()"

# 清空：删掉主库即可（重启后自动重建空库）；-wal/-shm 一起删更干净
rm -f data/zhiji.db data/zhiji.db-wal data/zhiji.db-shm
```

数据库路径可用 `ZHIJI_DATABASE_PATH` 覆盖。

## 接入真实模型

任何 OpenAI 兼容平台（DeepSeek / OpenAI / …），配置写进项目根目录 `.env`（Git 忽略，启动时自动加载）：

```bash
uv sync --extra openai
# .env 示例（DeepSeek-V4.1-Flash）
# ZHIJI_LLM_PROVIDER=openai
# ZHIJI_MODEL=deepseek-flash
# ZHIJI_OPENAI_BASE_URL=https://api.deepseek.com/v1
# ZHIJI_OPENAI_API_KEY=你的密钥
# ZHIJI_MAX_OUTPUT_TOKENS=4096
# ZHIJI_TOOL_TIMEOUT=60
```

环境变量清单见 [.env.example](.env.example)。注意：推理型模型务必设  
`ZHIJI_MAX_OUTPUT_TOKENS=4096`，避免输出被"思考"吃光导致空回答。

## 测试、评测与诊断

```bash
uv run pytest -q --basetemp=/tmp/sg-pytest   # 244 passed（本机沙箱须指定 basetemp）
uv run ruff check src tests scripts

# 评测门禁（有基线时掉超过容差 → 退出码 1）
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json \
  --baseline evals/baselines/retrieval.json
uv run zhiji-eval intent --dataset evals/datasets/intent.json \
  --baseline evals/baselines/intent.json

# 回合诊断（把一次会话读成诊断树，归因到 检索/工具/模型 层）
uv run zhiji-trace --thread <thread_id>
```

当前基线：检索 **Hit@3 = 1.0 / MRR = 1.0**、意图 **准确率 = 1.0**。全部自动测试与评测  
都跑在确定性 Mock 上，**零 API 消耗**。

前端质量门禁（沙箱内 `npm run build` 会被拦，用这两个替代）：

```bash
cd frontend && npx tsc --noEmit && npx eslint src
```

## 项目结构

```text
zhiji/
├── src/zhiji/
│   ├── domain/            纯领域逻辑（不依赖框架 / DB）
│   │   ├── scheduling.py     间隔重复 + 掌握度
│   │   ├── memory.py         长期记忆抽取
│   │   ├── quiz.py           出题规则（难度三档 / 提示词 / 模板）
│   │   ├── note_style.py     Markdown 笔记写作规范（注入提示词与工具描述）
│   │   ├── retrieval.py      切块 + RRF 融合
│   │   ├── planning.py       规划启发式与解析
│   │   ├── model_routing.py  模型档位选择
│   │   ├── evaluation.py     Hit@K / MRR 等评测指标
│   │   ├── guardrails.py     输入/输出护栏规则
│   │   └── models.py / errors.py
│   ├── application/       用例编排 + 端口（LangGraph 在这层）
│   │   ├── ports.py          对外部世界的 Protocol
│   │   ├── graph.py / routing.py / tools.py / state.py
│   │   ├── learning_service.py    学习闭环用例
│   │   ├── schedule_service.py    日程排期用例（确定性最早空档算法）
│   │   ├── image_notes.py         图片 → 规范 Markdown 视觉转写
│   │   ├── question_writer.py     模型写题、失败回退模板
│   │   ├── planner.py / evaluation.py / trace.py / guardrails.py
│   │   └── tool_runner.py / context.py
│   ├── infrastructure/    适配器（端口的实现）
│   │   ├── knowledge.py              SQLite + 混合检索
│   │   ├── learning_repository.py    错题/练习/掌握度/记忆
│   │   ├── chat_repository.py        项目/会话/消息/附件
│   │   ├── schedule_repository.py    日程任务
│   │   ├── usage_repository.py       token 用量记账
│   │   ├── mcp_client.py / mcp_bridge.py
│   │   └── embeddings.py / extract.py / llm.py
│   ├── interfaces/        入口（组合根）
│   │   ├── api.py            FastAPI + SSE（全部端点）
│   │   ├── cli.py / demo.py / evals.py / trace.py
│   └── config.py
├── evals/             评测数据集与基线（datasets/ + baselines/）
├── frontend/          Next.js 16 界面（Tailwind + Markdown/KaTeX + 流式）
│   └── src/
│       ├── app/           7 个路由（聊天 / 知识库 / 笔记 / 练习 / 错题 / 今日复习 / 日程）
│       ├── components/    AppShell · Chat · ChatsSection · KnowledgeTree · SchedulePickers · Markdown · ui
│       └── lib/api.ts     接口封装（含两个 SSE 解析器）
├── tests/             244 个自动测试（Mock，零 API 消耗）
├── scripts/dev.sh     一键起前后端
├── CHANGELOG.md       版本更新日志
├── data/              SQLite 库 + 附件 + 备份（git 忽略）
└── docs/              架构设计 / 使用指南 / 交接文档 / 接口一览
```

## 路线图

- **M1（已完成）**：状态图回合 · 意图路由 · 工具最小权限 · 学科知识库检索 · HITL 沉淀 · 检查点 · 流式 · Mock/真实双模型 · FastAPI/SSE · Next.js 界面 · 自动测试。
- **M2（已完成）**：向量检索 + RRF 混合排序；知识库上传接口。
- **M3（已完成）**：学习闭环——错题带学科、出题（失败回退模板）、间隔重复、掌握度、长期记忆、今日复习。


- **M4（已完成）**：资料上传与解析（TXT / Markdown / PDF / 图片视觉转写）；练习与错题界面；出题难度分层。
- **M5（已完成）**：评测门禁与回合 trace 诊断。
- **M6（已完成）**：护栏 · 工具执行可靠性 · 上下文压缩。
- **M7（已完成）**：规划 · 模型路由 · 成本控制。
- **M8（已完成）**：MCP 外部工具。
- **M9（已完成）**：会话系统（项目空间 + 记忆隔离 + 附件 + 过程流）、知识库 Obsidian 式阅读、日程（时间轴 + 收件箱）。
- **M10（已完成）**：信息架构重组——「练习复习 + 错题本」合并为**错题练习**（一页两 tab：错题本 / 专项练习，误区带错误类型 + 智能分类 + 选定错题出变式题）；聊天更名 **AI 对话**、「新对话」收进面板右上角；**课程空间**取代项目空间（新对话必选课程 + 常用课程引导，系统保留隐藏兜底空间「未归类」）。
- **M11（已完成）**：检索与入库强化——**智能检索**（模型选库 / 手动指定两模式 + 选库条内联新建）；**原样文件秒传 + 懒解析**（PDF/Word/PPT/Excel 落盘不解析，阅读器点「解析入库」建索引）；**markitdown 影子文本引擎**（PDF 按物理页、PPTX 按 slide 逐页切块带页码出处，魔数校验挡损坏文件）；**智能沉淀**（入库前模型提炼）；过程面板**手风琴简约化 + 单行活动模式**；PDF 智能格式化；右键菜单三形态。
- **M12（已完成）**：学习周报 + 检索增强——**本周概览**（提问/作答/错题/日程完成四卡 + 每日提问柱图 + 掌握度升降，确定性聚合零模型调用）；**DeepSeek 原生联网搜索**（服务端搜索+抓网页全文+基于全文整理答案，自动启用，回落博查/Tavily/双引擎，结果按概念覆盖过滤）；检索四连修（**jieba 词级查询**消灭跨词 gram、**结构化切块**按 Markdown 标题、**trafilatura** 正文抽取、**Embedding 可插拔**+故障降级）。
- **M13（已完成）**：检索召回扩写——**同义词 / 中英对照扩写**（内置等价术语组，「本征值」能搜到写着「特征值」的资料、「queue」能搜到「队列」；`ZHIJI_SYNONYMS_FILE` 可加自己课程的叫法）；**两字词短词召回**（「矩阵」「秩」「导数」进不了 trigram 索引，改走按命中覆盖度排序的 LIKE 路）；RRF 支持**通道权重**（扩写路降权）；修 AI 对话发送回调漏依赖导致的检索模式偶发不生效。
- **下一步候选**：扫描件视觉兜底 · 多用户隔离。（日程 × 学习闭环联动已由用户否决：日程是独立的每日规划工具，不与错题/复习联动。）

## 文档

- [AGENTS.md](AGENTS.md)：AI 编码 Agent 入口指令（命令/硬规则/坑，精简版）
- [架构设计](docs/架构设计.md)：图结构、状态模型、检索与权限、会话/日程设计、取舍与替代方案
- [使用指南](docs/使用指南.md)：安装、界面导览、常见问题
- [接口一览](docs/参考/API一览.md)：全部端点与 SSE 协议
- [交接文档](docs/交接文档.md)：现状快照、工作队列、坑清单与开发规则
- [更新日志](CHANGELOG.md)：M1~M13 各批次改了什么
- [文档导航](docs/README.md)
