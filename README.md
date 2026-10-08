# StudyGraph

**用 [LangGraph](https://langchain-ai.github.io/langgraph/) 编排的个人学习助理**——把聊天、学科知识库、检索、错题沉淀和出题复习，串成一条可以断点续跑的闭环。

StudyGraph 面向大学生：平时把资料分学科存进去、聊天随手沉淀笔记；期末让助手检索资料讲解、从错题和知识库自动出题。它把 LangGraph 的**状态机、检查点、Human-in-the-Loop 与流式输出**用在真实的学习流程上。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 🧭 意图路由 | 每条消息先判意图（讲解 / 练习 / 进度 / 检索 / 计算 / 闲聊），路由到对应子智能体 |
| 🧩 显式状态图 | 一次回合就是一张 LangGraph 状态图：`route → agent ⇄ tools`，循环与分支都写在明面上 |
| 🛡️ 工具最小权限 | **双层生效**：schema 层只给模型看允许的工具，执行层再拦一次黑名单 |
| 🔎 学科知识库 RAG | SQLite + FTS5 **trigram** 中文检索 + **向量余弦相似度**，两路用 **RRF** 融合；中文查询拆 3-gram，短词 LIKE 兜底，结果带出处 |
| 📥 资料上传 | TXT / Markdown / PDF 抽文本入库（PDF 走 `pypdf`），超限拒绝 |
| ✋ Human-in-the-Loop | "沉淀进知识库"这类写操作会先 `interrupt()` 请求确认，确认后才落库 |
| 🎓 学习闭环 | 错题带学科 → 出题（模型写题，失败回退模板）→ 练习自评 → 间隔重复排期 + 掌握度 |
| 🧠 长期记忆 | 从对话抽取事实注入提示词（标注"数据而非指令"） |
| 🗓️ 今日复习 | 汇总到期题 / 薄弱学科 / 近期误区，给出"今天做什么" |
| 💾 断点持久化 | `AsyncSqliteSaver` 检查点：会话可续、HITL 可恢复 |
| 🌊 流式输出 | 通过 LangGraph 的 `messages` 流模式逐块输出 |
| 🖥️ Web 聊天界面 | Next.js 16 + React 19：Tailwind、Markdown/KaTeX 渲染、流式打字、HITL 确认弹窗 |
| 🔌 HTTP / SSE 接口 | FastAPI 把图暴露成 `/api/chat/stream`、`/api/chat/resume` 与知识库接口 |
| 🤖 双模型适配 | 默认确定性 Mock（零成本），可切任意 OpenAI 兼容平台 |

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

| 层 | 目录 | 允许依赖 | 内容 |
| --- | --- | --- | --- |
| 领域 Domain | `domain/` | 仅标准库 | 间隔重复、掌握度、出题规则、RRF 融合、记忆抽取 |
| 应用 Application | `application/` | 领域 + 端口 | 用例编排、**端口 Protocol**、LangGraph 图与工具 |
| 基础设施 Infrastructure | `infrastructure/` | 应用 / 领域 | SQLite、Embedding、LLM、文件解析（端口的实现） |
| 接口 Interfaces | `interfaces/` | 全部 | FastAPI、CLI（**组合根**，负责装配） |

- 应用层只依赖 `application/ports.py` 里的 **Protocol**（`KnowledgePort` /
  `LearningRepositoryPort` / `EmbeddingPort` / `ChatModelPort`），不 import 任何具体实现——
  换数据库、换模型、换检索都不用改业务代码。
- 领域层是纯逻辑：测它不用起数据库、不联网。

## 快速开始

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run studygraph "帮我算一下 7 * 9"
```

预期输出：

```text
（模拟模型）根据工具返回的结果：63
```

沉淀一条笔记（写操作会请求确认，`--yes` 自动同意）：

```bash
uv run studygraph "记住：我在准备月底的微积分测验" --yes
uv run studygraph "我的笔记里怎么讲微积分测验的？"
```

### 启动 Web 界面（推荐）

```bash
./scripts/dev.sh
```

打开 <http://localhost:3000>：左侧是学科知识库（可勾选限定检索范围），右侧聊天，
回答用 Markdown/KaTeX 渲染并**流式打字**；当助手要保存笔记时，会弹出**确认框**
（Human-in-the-Loop），确认后才落库。后端在 `8011`，前端指向它，可用
`NEXT_PUBLIC_API_BASE` 覆盖。

> 前端需要 npm 依赖：首次先在 `frontend/` 里 `npm install`。

## 接入真实模型

任何 OpenAI 兼容平台（DeepSeek / OpenAI / …）：

```bash
uv sync --extra openai
export STUDYGRAPH_LLM_PROVIDER=openai
export STUDYGRAPH_MODEL=deepseek-chat
export STUDYGRAPH_OPENAI_BASE_URL=https://api.deepseek.com/v1
export STUDYGRAPH_OPENAI_API_KEY=你的密钥
export STUDYGRAPH_MAX_OUTPUT_TOKENS=4096
uv run studygraph "讲解一下导数的几何意义"
```

环境变量清单见 [.env.example](.env.example)。

## 测试与检查

```bash
uv run pytest -q            # 69 passed
uv run ruff check src tests
```

全自动测试跑在确定性 Mock 上，**零 API 消耗**。

## 项目结构

```text
studygraph/
├── src/studygraph/
│   ├── domain/            纯领域逻辑（不依赖框架 / DB）
│   │   ├── scheduling.py     间隔重复 + 掌握度
│   │   ├── memory.py         长期记忆抽取
│   │   ├── quiz.py           出题规则（提示词 / 解析 / 模板）
│   │   ├── retrieval.py      切块 + RRF 融合
│   │   └── models.py / errors.py
│   ├── application/       用例编排 + 端口（LangGraph 在这层）
│   │   ├── ports.py          对外部世界的 Protocol
│   │   ├── graph.py / routing.py / tools.py / state.py
│   │   ├── learning_service.py   学习闭环用例
│   │   └── question_writer.py    模型写题、失败回退模板
│   ├── infrastructure/    适配器（端口的实现）
│   │   ├── knowledge.py      SQLite + 混合检索
│   │   ├── learning_repository.py  学习数据的 SQLite 仓储
│   │   ├── embeddings.py / extract.py / llm.py
│   ├── interfaces/        入口（组合根）
│   │   ├── api.py            FastAPI + SSE
│   │   └── cli.py            命令行
│   └── config.py
├── frontend/          Next.js 16 聊天界面（Tailwind + Markdown/KaTeX + 流式）
├── tests/             69 个自动测试（Mock，零 API 消耗）
├── scripts/dev.sh     一键起前后端
└── docs/              架构设计与使用指南
```

## 路线图

- **M1（已完成）**：状态图回合 · 意图路由 · 工具最小权限 · 学科知识库检索 · HITL 沉淀 · 检查点 · 流式 · Mock/真实双模型 · FastAPI/SSE 接口 · Next.js 聊天界面 · 自动测试。
- **M2（已完成）**：向量检索 + RRF 混合排序；知识库上传接口。
- **M3（已完成）**：学习闭环——错题带学科、从错题/知识库出题（模型写题失败回退模板）、间隔重复排期、掌握度、长期记忆、今日复习规划。
- **M4（进行中）**：资料上传与解析（TXT / Markdown / PDF）已完成；待做：复习 / 错题界面、多用户隔离、出题难度分层。

## 文档

- [架构设计](docs/架构设计.md)：图结构、状态模型、检索与权限设计、取舍与替代方案
- [使用指南](docs/使用指南.md)：安装、运行、常见问题
- [文档导航](docs/README.md)
