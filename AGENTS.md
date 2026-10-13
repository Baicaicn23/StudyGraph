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
uv run pytest -q --basetemp=/tmp/sg-pytest   # 249 passed（Mock 零 API 消耗）
uv run ruff check src tests
cd frontend && npx tsc --noEmit && npx eslint src && cd ..
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json --baseline evals/baselines/retrieval.json
uv run zhiji-eval intent --dataset evals/datasets/intent.json --baseline evals/baselines/intent.json
```

- git 推送走代理隧道：`GIT_SSH_COMMAND="ssh -o ProxyCommand='/usr/bin/python3 ~/.ssh/gh-connect.py %h %p'" git push`
- 后端联网（web_search）需带代理 env 启动：`HTTP(S)_PROXY=http://127.0.0.1:8086`

## 架构边界（三句话）

- `src/zhiji` 分层：interfaces（API/SSE）→ application（编排/服务/JSON 模式）→ domain（纯函数：路由/切块/RRF）→ infrastructure（SQLite/LLM/搜索/Embedding）；frontend/ 用 Next.js App Router + Tailwind，无组件库（Radix Primitives 做弹层基座 + lucide 图标）。
- 知识库检索**四路**（原查询 FTS + 同义/中英扩写 FTS + 两字词 LIKE + 向量），RRF **加权**融合（扩写路 0.5 降权）——扩写词表在 `domain/synonyms.py`（`ZHIJI_SYNONYMS_FILE` 可追加），权重写死在 `KnowledgeStore.search()`。**加能力请加通道，别改 `_query_terms()`**（会动评测基线）。文档入库走"原样秒传 + markitdown 懒解析"（PDF/PPT 逐页切块带页码出处）。
- LLM 调用一律经 `build_chat_model`：思考恒最大档（DeepSeek 用 `thinking` 开关、GLM 加 `reasoning_effort`，白名单 provider 才附加）；结构化输出走 `application/json_mode.py`。
- 教学人格**分层**：总纲 `TEACHING_CHARTER`（三条红线 + 输出规格 + 技术过程内隐 + 禁止清单，全角色共享）→ `AgentProfile.system_prompt`（角色专属，讲解/错题/规划骨架挂这里）。`build_system_prompt` 拼接**稳定前缀在前、动态内容在后**（缓存友好，勿打乱）。改人格文案后跑 `tests/test_agent_modules.py`（断言各段真进了提示词）。

## 硬规则（never / always）

- **绝不**：无验证声称完成、绕过评测门禁、把"计划中"写成"已完成"、泄露 Secret、未备份就做破坏性操作。
- **绝不碰** `data/` 与 `.env` 里的 Secret；破坏性操作前先备份到 `data/backups/`。
- **测试全 Mock 零 API 消耗**；`tests/conftest.py` 的环境隔离与 chdir 勿动。
- **前端设计/排版必须先画示意图经用户确认**，再写代码（用户拍板的铁律；用户用截图反馈）。
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
- **新增工具必须同步 `domain/guardrails.py` 的 `_TOOL_LEAK_MARKERS`**（拦回复正文里的内部工具名，属「技术过程内隐」执行层兜底）；漏挂由 `test_tool_leak_markers_cover_registry` 抓出来。
- **`agent-browser` 必须打开 `http://localhost:3000`，不要用 `127.0.0.1`**：Next 16 把后者当跨源拦截 `/_next/hmr` → 页面**不 hydrate** → 所有按钮点了没反应（HTML/JS 全 200，极易误判成业务 bug）。且 `agent-browser eval` 里的 `.click()` 合成事件不触发 React，必须用 `agent-browser click <sel>`。
- git push 需代理隧道（代理不在时先 `nc -z 127.0.0.1 8086` 探测）。

## 验证标准（声称完成前必跑）

- 上述 pytest / ruff / tsc / eslint 全绿，且给出命令输出。
- 涉及检索质量的改动跑评测门禁（retrieval + intent），无回归才算完成。
- 涉及界面的改动在浏览器实测（`agent-browser` 可用），并等用户截图确认。

## 已否决决策（防翻案，完整理由见 docs/交接文档.md 第八节）

- ❌ 日程×学习闭环联动（日程是独立每日规划工具）
- ❌ 思考强度选择 UI / 自定义模型 / 模型切换（思考恒 max）
- ❌ 对话跨项目移动（记忆按 project_id 隔离）
