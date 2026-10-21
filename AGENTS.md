# AGENTS.md — 知迹（AI Agent 项目指令）

> 面向 AI 编码 Agent 的项目指令。人类向交接（叙事/决策详述/数据恢复）见
> [docs/交接文档.md](docs/交接文档.md)；最近会话快照见 `.workbuddy/memory/SESSION-CONTEXT.md`。

## 项目一句话

大学生 AI 学习私教 + 学习管理台——**数字媒体科技作品及创意竞赛（赛道十三·智慧教育）参赛作品**。
LangGraph 显式状态图回合 + FastAPI + SQLite + Next.js 16（App Router + Tailwind）。
核心闭环：知识库沉淀 → 混合检索 → 出题 → 间隔重复 → 掌握度；日程独立管"何时做"。

## 常用命令（仓库根目录执行）

```bash
./scripts/dev.sh                             # 后端 8011 + 前端 3000（改后端代码必须重启，无 --reload）
uv run pytest -q --basetemp=/tmp/sg-pytest   # 284 passed（Mock 零 API 消耗）
uv run ruff check src tests
cd frontend && npx tsc --noEmit && npx eslint src && cd ..
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json --baseline evals/baselines/retrieval.json
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json --baseline evals/baselines/retrieval.json --no-rerank   # 消融：关精排看 MRR 差
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json --baseline evals/baselines/retrieval.json --embedding real   # 真向量复验（联网、有成本）
uv run zhiji-eval intent --dataset evals/datasets/intent.json --baseline evals/baselines/intent.json
uv run zhiji-demo --reset                    # 播种演示数据（含 assets/demo_materials/ 的 PDF/Word/PPT）
```

- 演示素材（PDF/Word/PPT/图片）在 `assets/demo_materials/`（**受版本控制**，内容全部自编）；重新生成用
  `uv run --with reportlab --with python-docx --with python-pptx --with pillow python scripts/build_demo_materials.py`
  ——依赖是**一次性**的，走 `uv run --with` 不进项目 venv。**素材正文不得换成教材扫描件或网上下载的文档**（版权口径见 `docs/作品集/参赛/05-来源与授权清单.md`）。

- git 推送走代理隧道：`GIT_SSH_COMMAND="ssh -o ProxyCommand='/usr/bin/python3 ~/.ssh/gh-connect.py %h %p'" git push`
- 后端联网（web_search）需带代理 env 启动：`HTTP(S)_PROXY=http://127.0.0.1:8086`
- ⚠️ **`./scripts/dev.sh` 会静默进 Mock 模式**：脚本里 `export ZHIJI_LLM_PROVIDER="${ZHIJI_LLM_PROVIDER:-mock}"`，而 `config.py` 用 `load_dotenv(override=False)` —— **已存在的环境变量不会被 `.env` 覆盖**，所以 `.env` 里写了 `openai` 也会被顶掉。要用真实模型必须**显式前缀**：`ZHIJI_LLM_PROVIDER=openai ./scripts/dev.sh`。启动时脚本会打印生效模式；也可 `curl -s http://127.0.0.1:8011/api/health` 看 `provider`。
- ⚠️ **后端没起时前端页面是空的**（不是 bug）：`next dev` 可以单独活着，但列表/知识库/课程空间全要后端数据。看到"页面啥都没有"先 `lsof -nP -iTCP:8011 -sTCP:LISTEN`。

## 架构边界（三句话）

- `src/zhiji` 分层：interfaces（API/SSE）→ application（编排/服务/JSON 模式）→ domain（纯函数：路由/切块/RRF）→ infrastructure（SQLite/LLM/搜索/Embedding）；frontend/ 用 Next.js App Router + Tailwind，无组件库（Radix Primitives 做弹层基座 + lucide 图标）。
- 知识库检索**四路**（原查询 FTS + 同义/中英扩写 FTS + 两字词 LIKE + 向量），RRF **加权**融合（扩写路 0.5 降权），再由**词面精排**（`domain/retrieval.py` `rerank_hits`：原查询覆盖 0.50 / 扩写覆盖 0.15 / 标题命中 0.35）重排序——精排**只调顺序、不增删候选**，`--no-rerank` 可关做消融——扩写词表在 `domain/synonyms.py`（`ZHIJI_SYNONYMS_FILE` 可追加），权重写死在 `KnowledgeStore.search()`。**加能力请加通道，别改 `_query_terms()`**（会动评测基线）。文档入库走"原样秒传 + markitdown 懒解析"（PDF/PPT 逐页切块带页码出处）。
- LLM 调用一律经 `build_chat_model`：思考恒最大档（DeepSeek 用 `thinking` 开关、GLM 加 `reasoning_effort`，白名单 provider 才附加）；结构化输出走 `application/json_mode.py`。
- 教学人格**分层**：总纲 `TEACHING_CHARTER`（三条红线 + 输出规格 + 技术过程内隐 + 禁止清单，全角色共享）→ `AgentProfile.system_prompt`（角色专属，讲解/错题/规划骨架挂这里）。`build_system_prompt` 拼接**稳定前缀在前、动态内容在后**（缓存友好，勿打乱）。改人格文案后跑 `tests/test_agent_modules.py`（断言各段真进了提示词）。

## 硬规则（never / always）

- **绝不**：无验证声称完成、绕过评测门禁、把"计划中"写成"已完成"、泄露 Secret、未备份就做破坏性操作。
- **绝不碰** `data/` 与 `.env` 里的 Secret；破坏性操作前先备份到 `data/backups/`。
- **测试全 Mock 零 API 消耗**；`tests/conftest.py` 的环境隔离与 chdir 勿动。
- **前端设计/排版必须先画示意图经用户确认**，再写代码（用户拍板的铁律；用户用截图反馈）。
- **删除类接口一律级联**（无外键，手写 SQL）：删误区→派生题、删资料/库→引用其片段的题、删项目→记忆+会话+附件+**检查点线程**、删会话→检查点线程。判据：**"它被删了，谁还指着它？"** 新增任何派生物时都要问一遍。
- **约束冲突翻译成 4xx**（`projects` / `practice_questions` / `memories` 三处 UNIQUE → 409）；**同一资源的归属校验状态码要一致**（会话 GET messages / PUT / DELETE 统一 404）。
- **用户已否决、别再做**：日程×学习闭环联动；思考强度选择 UI；自定义模型/模型切换接入（思考恒 max，不设选择）。

## 高频坑（每条都踩过；详版见 docs/交接文档.md 第六节）

- pytest 必须 `--basetemp=/tmp/sg-pytest`；改后端代码必须重启进程（无 --reload）。
- `npm run build` 被沙箱拦——用 `npx tsc --noEmit` + `npx eslint src` 替代。
- 新增 SSE 事件必须同步前端 `parseEvent` 分支，否则静默丢弃。
- **markitdown 对损坏文件兜底按纯文本读**——`extract.py` 的魔数校验（OOXML=PK/XLS=OLE2）勿删。
- **DeepSeek V4.1-Flash 对 reasoning_effort 分档无响应**——有效控制轴是 `thinking` 开关。
- **markitdown 之外**：`KnowledgeStore` 测试构造必须传 embedder；`attach_text_content` 的 pages 路径与盲切路径勿合并。
- 弹层用 Radix Popover：Trigger 与 Content 必须同 Root；平按钮触发加 `onPointerDown` stopPropagation 防双触发闪烁。
- contextvar 不跨 LangGraph 节点传播——agent/tools 两节点各自 set。
- 节点里写 SQLite 走 `asyncio.to_thread`（同步写会锁库）。
- `curl` 传中文 query 要 `--data-urlencode`；测 localhost 加 `--noproxy '*'`。
- conftest 隔离环境变量（真实 Key 不会泄漏进测试）；改名/删依赖后手删 `.venv/bin` 残留旧脚本。
- python 批量脚本用**绝对路径**：连续 cd 后相对路径会静默读写错文件。
- **BSD grep 不支持 `\|` 交替**（macOS）——别用它做多词搜索，用 `rg`/Grep 工具。
- **检索评测必须用 `LexicalHashEmbedding`，不要换回 `MockHashEmbedding`**：后者用 ±1 随机符号哈希，共享 n-gram 的两段文本余弦会互相抵消≈0，于是评测里的向量路变成**纯噪声**、还以 1.0 权重把真正命中的候选挤出候选池（曾导致同义题「本征值」莫名漏召回）。评测改用 +1 计数哈希后，四路召回才被公平度量；它只代表词面相似度，真实语义由接真模型的 UAT 验证。
- **新增工具必须同步 `domain/guardrails.py` 的 `_TOOL_LEAK_MARKERS`**（拦回复正文里的内部工具名，属「技术过程内隐」执行层兜底）；漏挂由 `test_tool_leak_markers_cover_registry` 抓出来。
- **工作区文件工具**：`_workspace_dir()` 必须返回 **resolve 过的绝对路径**——`_safe_resolve()` 返回绝对路径，两边不一致时 `path.relative_to(...)` 会在**写完文件之后**抛错，表现为"盘上有文件却报写入失败"。测试 fixture 传 `tmp_path`（绝对）测不出，改这里务必跑 `test_relative_workspace_root_matches_production`。`user_id` 是客户端可传的，必须经 `_safe_user_segment()` 压成单层目录名。
- **`ChatRequest` 的字段声明与 `body.X` 读取必须同时改**：pydantic 对**未声明的入参静默丢弃**，读它才 `AttributeError` → 500。`retrieval_mode` 曾漏声明 → 只要 `knowledge_bases` 非空就 500（「指定知识库」模式长期不可用、智能选库从未生效）。加接口参数时两处一起动。
- **LangGraph 检查点与会话是两套存储**：只删 `chat_sessions` 会留下能从正文还原的孤儿线程。删会话调 `graph.checkpointer.adelete_thread(thread_id)`，清理前用 `chat.count_sessions_with_thread()` 确认无其他会话共享该 thread_id。
- **`documents.kind` 是状态机**：`file`（秒传未解析）→ 解析后升级 `file_text`（**原件仍在盘上**）。按 `kind` 过滤的查询必须想清楚「两个状态是否都该算」——`get_document_file` 曾只认 `file`，导致「解析入库」后原件 tab / 下载原文 404（**解析前正常、解析后反坏**）。
- **`agent-browser` 必须打开 `http://localhost:3000`，不要用 `127.0.0.1`**：Next 16 把后者当跨源拦截 `/_next/hmr` → 页面**不 hydrate** → 所有按钮点了没反应（HTML/JS 全 200，极易误判成业务 bug）。且 `agent-browser eval` 里的 `.click()` 合成事件不触发 React，必须用 `agent-browser click <sel>`。
- **`agent-browser click` 的两个静默陷阱**（都踩过，且都报 `✓ Done` 让人以为成功）：① ref 必须带 `@` 前缀——`click @e58` 才行，写成 `click e58` 会被当成 CSS 选择器**静默失败**；② 元素在**可视区之外**时点击会落到空处，**必须先 `agent-browser scrollintoview @e58`** 再 click。另外**只支持 CSS / `@ref`，不支持 `text=` 选择器**（会报 Element not found）。判断点击是否真的生效：看后端日志有没有收到请求，或重新 `snapshot` 看 DOM 变没变——**别信 `✓ Done`**。
- 排查"点了没反应"的可靠姿势：`snapshot -i`（只列可交互元素）+ `eval` 里直接发一次 `fetch` 看接口通不通，两头一夹就能定位是"没点着"还是"请求失败"。
- git push 需代理隧道（代理不在时先 `nc -z 127.0.0.1 8086` 探测）。

## 验证标准（声称完成前必跑）

- 上述 pytest / ruff / tsc / eslint 全绿，且给出命令输出。
- 涉及检索质量的改动跑评测门禁（retrieval + intent），无回归才算完成。
- 涉及界面的改动在浏览器实测（`agent-browser` 可用），并等用户截图确认。

## 已否决决策（防翻案，完整理由见 docs/交接文档.md 第八节）

- ❌ 日程×学习闭环联动（日程是独立每日规划工具）
- ❌ 思考强度选择 UI / 自定义模型 / 模型切换（思考恒 max）
- ❌ 对话跨项目移动（记忆按 project_id 隔离）

## 答辩 PPT 与插图（2026-10-21 起）

**旧的答辩 PPT 已全部删除**（`知迹答辩/` kami 版、`知迹答辩-web/` html-ppt-skill 版，
两者视觉风格都被用户否决）。当前状态是：**内容结构、逐页规格与给豆包 Agent 的提示词均已完成，
成稿待制作**。

```bash
# 论文级方法示意图（SVG 源 + 高清 PNG）—— 改文案后重跑即可
uv run python scripts/make_overview_figure.py --png
# → docs/作品集/插图/知迹方法总览/知迹-方法总览.{svg,png}
```

  给豆包的那份提示词由脚本从它生成，**不要手改生成物**。
- **插图分两类，别混**：
  - **方法论图 / 架构图 / 带准确数字的图** → 必须手写 SVG（结构与数字要准，生图模型做不到）。
  - **氛围插画 / 封面场景** → 可用生图模型（豆包 Seedream 4.0 中文渲染约 98%，标题可直接写进图里）。
  - **数字永远不交给生图模型**（错一位就是编造数据），留在 PPT 里叠。
- Chrome headless 必须 `--headless=new --no-sandbox`（旧的 `--headless` 会 SIGTRAP）。
- **PPT 配套文档**（`docs/作品集/参赛/知迹答辩/`）：
  `STORY.md`（叙事 + 页间过渡句 + 数字口径）/ `DESIGN.md`（视觉规范）/
  `assets/配图提示词.md`（只需生 2 张氛围图）/ `README.md`（交付说明与改稿方法）。
  后续若有人接着做 PPT，**页序与文案以 `STORY.md` 为准，不要另起一套**。
- 用户偏好（已否决的别再做）：kami 纸感学术风「太空、留白多」→ 走**明亮浅色调**；
  插图要**3D 写实 / 摄影级质感**，不要扁平矢量示意图；**全篇不出现人物**。

