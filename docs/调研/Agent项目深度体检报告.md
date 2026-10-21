# Agent 项目深度体检报告

> **评审对象**：知迹（AI 学习私教与学习管理台）· LangGraph + FastAPI + SQLite + Next.js 16
> **评审人视角**：10 年经验 AI Agent 架构师 / 技术面试官
> **评审依据**：源码实读（`src/zhiji/` 全量 95 个文件）、`evals/` 评测集、284 项自动测试
> **评审日期**：2026-10-21

---

## 📊 一、项目水平画像与综合评级

### 综合评分：**7.2 / 10**

### 当前段位：**「接近生产级的个人级产品」**（高于早期原型，明显高于 Demo 玩具；尚未达到可交付多租户的生产系统）

给这个分不是因为功能多，而是因为**它做对了 Agent 工程里最难做对的那几件事**——显式状态图、工具双层权限、执行层 HITL、确定性评测门禁。这些是 90% 的"AI Agent 项目"里看不到的。

但它离生产级还差**一层观测能力和一层隔离能力**，这两层恰好是"个人用"和"给用户用"的分界线。

### 一句话毒舌总结

> **这是一套把「思考过程」管得很好的系统，却对「思考过程本身」几乎不可见。**
>
> 它的 trace 是**事后从消息历史里猜出来的**，不是运行时记录下来的。
> 你能知道"哪一步错了"，但不知道"这一步花了 1.2 秒还是 12 秒、烧了 3000 还是 30000 token、
> 是哪次重试救回来的"。这在个人 Demo 里看不出来，**在生产里等于盲飞**。

---

## 🌟 二、目前有什么（做得非常优秀的）

### 亮点 1：工具权限是**双层且执行层强制**——这是全项目最专业的设计

```python
# application/routing.py:294
def is_tool_allowed(profile: AgentProfile, name: str) -> bool:
    """执行层权限判定：即使模型硬发一个被禁工具，也在这里被拦下。"""
    if profile.deny_all:
        return False
    if not profile.mcp_enabled:
        from .tools import is_mcp_tool
        ...
```

```python
# application/graph.py（tools_node 内）
if not is_tool_allowed(profile, name):
    return ToolMessage(content=f"[tool_not_allowed] 当前模式下不允许调用「{name}」。", ...)
```

**为什么这是亮点**：绝大多数项目只在 **schema 层**裁剪工具（"不告诉模型有这个工具"），
然后就以为安全了。但 LLM 完全可能**幻觉出**一个被禁的工具名并真的发起调用。
这个项目做了 schema 层 + 执行层两道，且执行层那道是在**工具真的被执行之前**拦截，
拦截结果还回写成一条正常的 `ToolMessage`（而不是抛异常）——所以模型能"知道被拒了"并改道，
对话不会崩。

更细的一点：MCP 工具用 `mcp_` 前缀兜底（`mcp_enabled=False` 的子智能体，
即使模型幻觉出 MCP 工具也执行不了）。动态注册的工具名字运行时才知道、没法枚举，
用前缀拦是对的。

**这一条在面试里可以讲 3 分钟，而且是真东西。**

### 亮点 2：工具失败被**降级成工具消息**而不是炸掉回合

```python
# application/graph.py（tools_node 内）
except Exception as exc:  # noqa: BLE001 — 工具失败转成工具消息，不炸整回合
    return ToolMessage(content=f"[tool_error] {type(exc).__name__}: {exc}", ...)
```

配合 `application/tool_runner.py` 的重试策略：

```python
except TimeoutError:
    last_error = ToolTimeoutError("工具执行超时")
except (OSError, ConnectionError) as exc:
    last_error = exc
# 参数错误（ValueError）立即失败，重试没有意义
```

**为什么这是亮点**：这里体现了**成熟的成本意识**——只对"重试有意义"的错误（超时/网络抖动）
做**有界**退避重试（`retries=2`，`base_delay * 2**attempt`），对参数错误立刻失败。
很多项目写成"所有异常都重试 3 次"，那是在烧钱。

还有两处细节做对了：
- `GraphInterrupt` 被**显式原样上抛**（不能被当成工具错误吞掉）——这是 HITL 能工作的前提
- 同轮多个工具调用用 `asyncio.gather(..., return_exceptions=True)` **并发执行**，
  且**按原始顺序落库**（顺序稳定，便于回放）

### 亮点 3：评测是**确定性 + 有基线 + 能当门禁**的，不是"我跑了一下看着还行"

```bash
uv run zhiji-eval retrieval --dataset evals/datasets/retrieval.json \
  --baseline evals/baselines/retrieval.json
# cases: 35  hit_at_k: 0.9714  mrr: 0.9714  ✓ 无回归
```

**为什么这是亮点**：三个关键设计都做对了：
1. **强制确定性向量**（`LexicalHashEmbedding`，+1 计数哈希）—— 同一版本任何人跑出同样的分数。
   （这里踩过一个真实的坑：早期用 `MockHashEmbedding` 的 ±1 随机符号哈希，
   共享 n-gram 的文本余弦互相抵消≈0，向量路变成纯噪声还以 1.0 权重把真命中挤出候选池）
2. **有基线 JSON + 容差 0.05**，掉出容差**命令返回非零** → 能直接进 CI
3. **有消融开关**：`--no-rerank` 能看到关掉精排 MRR 从 0.9714 掉到 0.9571。
   这比"我的 MRR 是 0.97"强一个量级——**它证明了机制本身有用**。

### 亮点 4：规划是**真判断**，不是摆设

```python
# domain/planning.py
MAX_STEPS = 5

def is_complex(text: str) -> bool:
    """是否需要"先规划再执行"。短请求默认不需要（保持低延迟、低成本）。"""
    content = (text or "").strip()
    if len(content) >= 40:
        return True
    if any(marker in content for marker in _COMPLEX_MARKERS):
        return True
    separators = content.count("，") + content.count(",")
    return separators >= 2 and any(marker in content for marker in _SEQUENCE_MARKERS)
```

```python
# application/graph.py:169
async def plan_node(state: StudyState) -> dict[str, Any]:
    text = _last_human_text(state["messages"])
    if not is_complex(text):
        return {"plan": []}          # ← 简单请求直接跳过规划
    return {"plan": await build_plan(model, text)}
```

**为什么这是亮点**：很多项目的"规划"是给每个请求都让 LLM 先列一遍步骤，
延迟和成本双倍。这里是**规则先判需不需要，需要才走模型**，且计划步数有 `MAX_STEPS=5` 上限。
这是"成本意识"，和评测里的确定性向量是同一种思维。

### 亮点 5（额外）：单一数据源 + 可复跑的生成管线

`domain/retrieval.py` 的 `rerank_hits` / `rrf_fuse` 是纯函数；`domain/scheduling.py` 的
复习排期是纯函数（`again −10/0天`、`hard −3/1天`、`good +5/3天`、`easy +10/7天`，
掌握度 `clamp` 在 0–100）；`domain/memory.py` 的事实抽取是纯函数。
**测这些不用起数据库、不联网、不花 API 额度**——284 项测试全 Mock 零消耗。

---

## ⚠️ 三、差什么（致命缺陷）

### 缺陷 1（最致命）：**Trace 是事后推断的，不是运行时记录的**

```python
# application/trace.py
"""回合 trace：把一段会话历史读成"哪一步出了问题"的诊断。
这不是日志，而是**归因**..."""
```

`diagnose()` 从 `messages` 列表里**反推**责任层：

```python
def _is_error(content: str) -> bool:
    return (content.startswith("[tool_not_allowed]") or ...)

def _is_empty(content: str) -> bool:
    return "没有找到" in content or content.strip() == ""
```

**问题在于**：

| 生产需要知道的 | 现在能不能知道 |
|---|---|
| 哪一步失败了 | ✅ 能（这是它做得好的部分） |
| 每一步**耗时**多少 | ❌ **完全不知道** |
| 每一步烧了多少 **token** | ❌ 只有一个回合级的总量（`/api/usage`） |
| 哪个**模型档位**处理了哪一步 | ❌ 不知道 |
| **重试了几次**才成功 | ❌ 不知道（重试在 `run_tool` 内部，痕迹被吞掉） |
| 这次失败的**根因**是超时还是参数错 | ❌ 只有异常类型字符串 |
| **P95 延迟** | ❌ 无从算起（没数据） |
| 哪类 query **最容易**触发降级 | ❌ 得手工翻会话历史 |

而且**全文搜索确认**：项目里**没有接入任何第三方 tracing**——
无 LangSmith、无 OpenTelemetry、无 Arize/Phoenix。

```bash
# 可复现的核查命令（注意用词边界，否则 "summarize" 会被 "arize" 误命中）
grep -rniE "\blangsmith\b|\bopentelemetry\b|\btraceparent\b|\bspan_processor\b|\barize\b|\bphoenix\b" \
  src/zhiji/ --include="*.py"
# → 0 命中
```

（`uv.lock` 里出现 `langsmith` 是 **langchain 的传递依赖**，项目自身并未安装或使用它。）

**这在生产里意味着什么**：你上线后发现"用户说今天特别慢"，
你**没有任何数据**能回答"是检索慢了、模型慢了、还是工具重试了三次"。
唯一能做的是手工翻 `chat_messages` 表看 `steps` 字段。

**这正好是评委问你"最重要的一点"时的最短板。**

---

### 缺陷 2：**没有"连续失败熔断"，Agent 会在死循环里烧钱**

现在的循环控制只有**总轮次上限**：

```python
# application/graph.py:150
max_tool_rounds: int = 6,
...
# application/graph.py:305
def should_continue(state: StudyState) -> str:
    if getattr(last, "tool_calls", None) and state.get("tool_rounds", 0) < max_tool_rounds:
        return "tools"
    return END
```

有上限 = **有护栏**，这是对的。但**只有总量上限，没有连续失败上限**。

**故障场景**：某个工具（比如 `web_search`）持续 500 错误，或某个知识库查询反复返回空。
Agent 的典型反应是"再换个参数试一次"——它会**连续用不同参数调用同一个失败的工具**，
每次都拿到 `[tool_error]`，然后再调一次……**一直到撞满 6 轮上限**。

这 6 轮里：
- 每次都**真实调用了外部 API**（真花钱）
- 每次都**消耗了完整的一轮上下文**（真烧 token）
- 而**其中可能有 5 轮是纯粹的无用重试**

生产事故的典型形态就是这个：某个下游服务抖动，用户点了 10 次，
你付了 60 次 API 调用的钱，只得到 6 条一模一样的报错。

**缺的东西**：
1. **连续同工具失败计数** —— 同一工具连错 N 次（比如 3 次）就该中断整个工具循环，直接返回给用户
2. **失败模式指纹** —— 同样的错误重复出现，应该让 Agent 知道"这条路走不通了"
3. **错误去重/降噪** —— 6 条一模一样的 `[tool_error]` 进上下文，纯属浪费 context

---

### 缺陷 3：**记忆没有生命周期，是"只增不减"的黑洞**

```sql
-- infrastructure/learning_repository.py:60
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    project_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE (user_id, project_id, content)
);
```

表里**只有 `created_at`，没有有效期、没有状态、没有被替代关系**。
抽取逻辑是纯正则：

```python
# domain/memory.py
_EXPLICIT = re.compile(r"记住[：:]\s*(.+)")
```

**问题**：用户大二说"我在准备四级"，大三说"我在准备考研"——
两条记忆**同时存在于表里，也同时被注入提示词**。
模型收到的是：

```
[背景资料] 我在准备四级
[背景资料] 我在准备考研
```

**它不知道哪个是现在的。** 更糟的是，模型会**两件都当真**去回答，
可能一边讲四级词汇一边讲考研数学。

而注入记忆是**无条件的**（`build_system_prompt` 里无条件拼进去），
所以**过期的记忆会一直污染每一次对话**。用得越久越脏。

另外两个小问题：
- **抽取靠正则**：`"记住：X"` 之外的表达基本抓不到（"我下周要交作业"抓不到）
- **不用向量**：记忆是**全量字符串匹配注入**的，不是语义检索。
  记忆条数一多，提示词就膨胀，而且注入的是**不相关**的旧记忆

---

### 缺陷 4（部署面）：**单用户假设贯穿整个代码，无鉴权、无 CI、无结构化日志**

| 项 | 现状 | 生产后果 |
|---|---|---|
| **鉴权** | `grep -rniE "auth\|bearer\|Depends.*auth"` → **零命中** | 任何人都能调 `/api/chat`、读别人会话、读知识库 |
| **多租户** | `user_id` 是**客户端可传**的字段 | 改一下参数就能读别人的数据 |
| **CORS** | 硬编码 `allow_origins=["http://localhost:3000", ...]` | 上线必须改，且容易漏 |
| **日志** | `grep -rnE "logging\|getLogger\|structlog"` → **零命中** | 只有 `print`（CLI）和 SSE 事件（前端）。**服务器日志里没有请求链路** |
| **CI** | `.github/workflows/` **不存在** | 那个"能进 CI 的门禁"其实**没有 CI 在跑** |
| **DB 并发** | WAL + `busy_timeout=5000` | 单机够用；**多进程部署会撞锁**（SQLite 的硬限制） |
| **健康检查** | 有 `/api/health` | ✅ 这个有 |

**这一档是最容易被忽略的**：功能做得再好，**没有鉴权 = 不能给第二个用户用**。

---

## 🛠️ 四、如何脱离"玩具感"（三个代码级优化）

### 优化点 1：把 trace 从"事后猜"升级为"运行时记录"（收益最高）

**目标**：让每一步都有 **span + 耗时 + token + 模型 + 重试次数**。

**改法**：不动现有 `diagnose()`（它是好的归因逻辑，保留），**在它旁边加一层运行时记录**。

```python
# 新增 infrastructure/telemetry.py
from dataclasses import dataclass, field
import time

@dataclass
class Span:
    name: str
    started_at: float = field(default_factory=time.perf_counter)
    duration_ms: float | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0
    error: str | None = None
    children: list["Span"] = field(default_factory=list)

class Tracer:
    def __init__(self, thread_id: str): self.thread_id = thread_id; self.spans = []
    def span(self, name: str) -> "SpanCtx": ...
```

在 `graph.py` 的四个节点包一层：

```python
# agent 节点
with tracer.span("agent") as sp:
    result = await model.ainvoke(messages)
    sp.tokens_in = usage.get("input_tokens", 0)
    sp.tokens_out = usage.get("output_tokens", 0)
    sp.model = settings.model
```

在 `tool_runner.run_tool` 里把重试次数记进 span：

```python
for attempt in range(retries + 1):
    try:
        return await asyncio.wait_for(call(args), timeout=timeout)
    except TimeoutError:
        last_error = ToolTimeoutError("工具执行超时")
        span.retries = attempt + 1   # ← 新增
```

**关键**：span 随 `chat_messages.steps` 一起落库（**已有这个字段**，不用改表结构），
这样 `zhiji-trace` 命令从"猜"变成"读"。

**再进一步**：把 `Span` 序列化成 **OpenTelemetry 格式**，
接上 LangSmith / Phoenix / Jaeger——**这才是简历上能写的那句话**。
（约 150 行代码，是这个项目投入产出比最高的一步）

---

### 优化点 2：加"连续失败熔断 + 错误去重"

**目标**：工具连续失败 N 次就停，别烧满 6 轮。

```python
# application/graph.py 新增
_MAX_SAME_TOOL_FAILURES = 3

def _should_abort_tools(state: StudyState) -> str | None:
    """连续同工具失败达阈值 → 中断工具循环，把错误回给模型让它自己收场。"""
    recent = [m for m in state["messages"] if isinstance(m, ToolMessage)][-_MAX_SAME_TOOL_FAILURES:]
    if len(recent) < _MAX_SAME_TOOL_FAILURES:
        return None
    names = {getattr(m, "name", "") for m in recent}
    if len(names) == 1 and all(str(m.content).startswith("[tool_error]") for m in recent):
        return names.pop()
    return None
```

在 `should_continue` 里先查它：

```python
def should_continue(state: StudyState) -> str:
    if _should_abort_tools(state):
        return END          # ← 别再重试了，直接收场
    if getattr(last, "tool_calls", None) and state.get("tool_rounds", 0) < max_tool_rounds:
        return "tools"
    return END
```

**同时做错误去重**（在 tools_node 里）——连续相同的错误只保留第一次，
后续用 `[tool_error] 与上一次相同，已省略` 代替。省 context，也省模型误以为有新信息：

```python
if error_text == last_error_text:
    content = "[tool_error] 与上一次相同（已省略），请换思路。"
```

---

### 优化点 3：给记忆加生命周期，并从"全量注入"改成"按需检索"

**目标**：解决"大一小两道冲突"和"记忆只增不减"。

**第一步：改表结构**（加状态机，不加字段也能先做）

```sql
ALTER TABLE memories ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
-- active / superseded / expired
ALTER TABLE memories ADD COLUMN valid_until REAL;
ALTER TABLE memories ADD COLUMN supersedes INTEGER REFERENCES memories(id);
```

**第二步：写入时做冲突消解**（不是靠模型，是靠规则 + 时间）

```python
# application/learning_service.py
def remember(self, user_id: str, project_id: str, facts: list[str]) -> None:
    for fact in facts:
        # 同类事实（同 project）的新记忆 → 旧的标 superseded
        old = repo.find_active(user_id, project_id, topic_of(fact))
        repo.supersede(old)
        repo.insert(user_id, project_id, fact)
```

`topic_of()` 可以先用关键词规则（"准备X" / "我是X" / "目标X"）——
**先把"同槽位互斥"做出来，比上向量库更立竿见影**。

**第三步：注入时按相关性筛，而不是全量拼**

现在 `build_system_prompt` 是无条件拼所有 active 记忆。
改成：**先用检索挑 Top-K 相关记忆**（可以复用项目里已经写好的 `knowledge_search`
那套四路召回——**这是现成的、本项目最大的优势**）：

```python
# 只注入与当前问题相关的 3-5 条，而不是全部
relevant = self.knowledge.search(query=question, user_id=user_id, limit=5)
```

**第四步（可选）：加过期策略** —— 记忆带 `valid_until`，
或按"多久没被引用就衰减"（用 `mastery_snapshots` 已有的时间序列做依据）。

---

## 🚀 五、下一步的进阶挑战（写进简历 & 拿下面试）

### 先说结论：**不要加多 Agent 协作**（会掉分）

多 Agent 是简历上最容易写、面试里最容易被问倒的东西。
评委问"多 Agent 协作你怎么解决的 Agent 间通信、冲突、局部失败"，
答不上来就是负分。**你现在的单 Agent + 显式状态图，比硬凑多 Agent 强得多。**
（调研文档里已经写过这个判断，理由是"单用户学习场景，子任务不需要各自吃大量上下文；
拆了只会把可解释这个优势搭进去"）

### 该加的模块，按 ROI 排序：

#### ① 任务级评测（Evaluation Harness）—— **最高优先级，面试最认**

**现状**：只有「检索命中没」（Hit@3/MRR）和「意图分类对不对」（accuracy）。
**缺的是**：「这次复习到底有没有用」——**任务成功率**。

**怎么加**（关键是用**确定性状态校验**，不用 LLM 判分）：

```python
# evals/datasets/review_tasks.json
{
  "id": "task-001",
  "setup": [                      # 前置状态（直接写库，不走 LLM）
    {"action": "seed_mistake", "library": "高等数学", "error_type": "概念混淆"},
    {"action": "seed_document", "title": "微积分复习提纲", "body": "..."}
  ],
  "steps": [                      # Agent 要完成的动作序列
    {"tool": "mistake_search", "expect": {"contains": "概念混淆"}},
    {"tool": "generate_question", "expect": {"difficulty": "basic"}},
    {"tool": "answer", "expect": {"mastery_delta": -10}}
  ],
  "assert_state": {               # 终态断言：查库验，不问模型
    "question_count": 1,
    "mastery": 60,
    "due_at_not_null": true
  }
}
```

**为什么这个在面试里值钱**：
- 面试官问"你怎么知道它今天比昨天聪明"，你的答案从"跑个评测看分数"升级成
  "**任务级成功率 + pass^k 稳定性**"
- 引入 **pass^k**（同一任务跑 k 次全对才算过）—— 暴露**随机性**。
  你的 Agent 现在跑 5 次可能有 4 次对 1 次错，pass@1 = 1.0 但 pass^5 = 0，
  **这才是真实的生产可靠性**

配套要加的：**难例考卷**。现在 35 题的检索基线已经饱和（0.9714），
加难例（长文档、跨库同名、强干扰项）才测得出差别。

#### ② 运行时 Tracing + OpenTelemetry —— 面试官一听就懂

见优化点 1。**加一个 `spans` 表 + OTel exporter**，
简历上就能写：

> 接入 OpenTelemetry，全链路 span 覆盖检索/工具/模型三层，
> 支持按 trace 回放任意一次会话；基于 span 数据做 P95 延迟与 token 成本看板。

#### ③ 记忆生命周期 + 语义检索 —— 回应"你的 Agent 记得太多但记不准"

见优化点 3。这个模块做完了，**面试里可以聊 LongMemEval / 记忆衰减**，
是很少人能答上来的深度。

#### ④ 成本与限流（生产必备，面试必问）

现在有 **token 记账 + 日预算**（超限阻止真实调用），
但**没有**：
- **单用户 QPS 限流**（一人狂点就能打爆你的 API Key）
- **并发上限**（asyncio.gather 并发工具调用，上游扛不住就一起挂）
- **多级熔断**（连续失败后主动降级到缓存/兜底，而不是继续打）
- **成本归因到会话**（哪个用户/哪个功能烧的钱）

加一个 `infrastructure/rate_limit.py`（令牌桶）+ 每用户并发信号量，
再把成本按 `user_id` × `session` 拆开，**这就是"生产级"的实感**。

#### ⑤ 多用户与鉴权（如果想真的给别人用）

补 **JWT 鉴权中间件 + 请求级 user_id 推导**（现在是客户端可传，这是越权漏洞）。
**注意**：项目已经做了"同一资源归属校验状态码一致（统一 404）"，
说明**多租户的数据访问层设计是对的**——缺的只是**入口的鉴权**。
工作量比想象中小：加一个依赖 + 把 `user_id` 从 `body` 改成从 token 解。

#### ⑥ 值得做但不要吹的：Agent 自我纠错（Reflection）

调研文档里判断"反思节点"不值得做（没有独立外部判据，答案对错由学科事实决定，
模型自评比生成更不可靠）——**这个判断是对的，别改**。
但**工具层面的自我纠错**值得做：优化点 2 的熔断 + 错误去重，
以及**工具错误码分类**（参数错 vs 超时 vs 权限）喂回给模型，
让它自己换策略。这比"加一个反思节点"实在得多。

---

## 📋 附：维度评分表

| 维度 | 得分 | 一句话点评 |
| --- | --- | --- |
| **1. 核心架构与规划能力** | **7.5** | 显式状态图 + `max_tool_rounds=6` 上限是真护栏；`plan` 节点有 `MAX_STEPS=5` 且规则判定"是否需要规划"（`is_complex`：长度/关键词/序列词），**是真规划不是摆设**；但**缺连续失败熔断**（缺陷 2），且复杂多步任务的 plan 质量从未被评测验证过 |
| **2. 工具调用与异常处理** | **8.0** | 双层权限 + 分类重试 + 降级成 ToolMessage + 并发保序，**四样都做对了**，是本项目最强的一维；扣分在工具侧**没有业务级参数校验**（`@tool` 靠类型注解生成 pydantic schema，类型对但取值域不校验——比如 `web_search(max_results=99999)` 没人拦） |
| **3. 记忆与状态管理** | **6.0** | 上下文压缩（24 条上限 / 保留 14 / 抽取式摘要 ≤240 字，不拆散工具调用对）**做得对**；但长期记忆是**正则抽取 + 全量注入 + 无生命周期**（缺陷 3），扣分最多的一维 |
| **4. 可观测性与评测** | **6.5** | 评测侧**优秀**：确定性向量 + 基线 + 容差门禁 + 消融开关，35 题检索 + 15 句意图；观测侧**弱**：trace 是事后推断、无 span/延迟/token 归因、无第三方接入、无 CI（缺陷 1） |
| **5. 工程化与部署** | **7.5** | 六边形分层 + Protocol 端口 + 纯函数 domain（可单测）+ WAL + 284 项零消耗测试 = 工程质量在线；扣分在**无鉴权、无 CI、无结构化日志、CORS 硬编码**（缺陷 4） |
| **加权综合** | **7.2** | **接近生产级的个人级产品** |

### 距离生产级的距离（一句话）

> **补上「运行时 tracing」和「鉴权 + 限流」这两层，就是能真给第二个用户用的系统。**
> 剩下的差距（任务级评测、记忆生命周期）是"更聪明"的问题，不是"更可靠"的问题——
> 而生产事故几乎全部出在后者。

---

**免责**：本报告基于源码静态审读 + 评测复现（284 passed / 检索 0.9714 / 意图 1.0），
未做压力测试与真实流量验证；生产结论需结合实际部署环境复核。
