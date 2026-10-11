"""Agent 可调用的工具。

内置工具：
- `calculator`：安全算术求值，杜绝直接 eval 注入。
- `knowledge_search`：在学科知识库里检索，返回带出处的片段。
- `mistake_search`：检索学生的错题/误区记录并做频次归因（只读）。
- `save_note`：把内容沉淀进某个学科库——**会先 `interrupt()` 请求用户确认**
  （Human-in-the-Loop），确认后才落库。

工具依赖的是**端口**（`KnowledgePort` / `LearningRepositoryPort`），不是具体实现。
两样"本轮会话上下文"用 contextvar 传递，避免污染模型可见的参数 schema：
本轮选中的知识库、当前学生 user_id。注意 LangGraph 各节点在独立 context 里
执行，`graph.py` 的 agent 节点和 tools 节点都要各自 set 一次。
"""

from __future__ import annotations

import ast
import contextvars
import operator
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt

from .ports import KnowledgePort, LearningRepositoryPort

_knowledge: KnowledgePort | None = None
_learning: LearningRepositoryPort | None = None
_current_libraries: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "studygraph_current_libraries", default=None
)
_current_user: contextvars.ContextVar[str] = contextvars.ContextVar(
    "studygraph_current_user", default="local"
)

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}


def configure(
    knowledge: KnowledgePort, learning: LearningRepositoryPort | None = None
) -> None:
    """由组合根注入知识库与学习仓库实现。"""

    global _knowledge, _learning
    _knowledge = knowledge
    _learning = learning


def get_knowledge() -> KnowledgePort:
    if _knowledge is None:
        raise RuntimeError("工具尚未配置知识库：请先调用 tools.configure(...)")
    return _knowledge


def set_current_libraries(libraries: list[str] | None) -> None:
    _current_libraries.set(list(libraries) if libraries else None)


def set_current_user(user_id: str) -> None:
    _current_user.set(user_id or "local")


def _format_number(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        operation = _BIN_OPS.get(type(node.op))
        if operation is None:
            raise ValueError("不支持的运算符")
        return operation(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +_eval_node(node.operand)
    raise ValueError("表达式只允许数字、括号和四则运算")


def safe_eval(expression: str) -> float:
    """只做算术的安全求值：解析成语法树后按白名单运算，不做真实 eval。"""

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("算式语法有误") from exc
    return _eval_node(tree.body)


@tool
def calculator(expression: str) -> str:
    """计算一个数学表达式，例如 "7 * 9" 或 "(2 + 3) / 4"。只做算术，不解释。"""

    try:
        return _format_number(safe_eval(expression))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        return f"计算出错：{exc}"


@tool
def knowledge_search(query: str) -> str:
    """在学生的学科知识库里做全文检索，返回相关片段和出处。当问题可能与
    学生自己上传/沉淀的资料有关时使用（例如"我的笔记里怎么说的"）。"""

    libraries = _current_libraries.get()
    hits = get_knowledge().search(query, libraries=libraries, limit=4)
    if not hits:
        return "知识库里没有找到相关片段。这部分内容学生还没有沉淀到知识库。"
    blocks = [f"【{hit.library} / {hit.title}】{hit.content}" for hit in hits]
    return "\n\n".join(blocks)


@tool
def mistake_search(query: str = "") -> str:
    """检索学生的错题/误区记录，按关键词过滤并统计同类错误的频次。
    当学生提到"错题 / 误区 / 易错点 / 我哪里错了"或需要针对薄弱点
    出题时使用；不传关键词则返回最近误区概览。这是只读工具。"""

    if _learning is None:
        return "错题记录暂不可用。"
    user_id = _current_user.get()
    feedbacks = _learning.list_feedback(user_id, limit=50)
    if not feedbacks:
        return "错题本里还没有记录，可以先让学生记录一条误区。"

    keyword = (query or "").strip()
    if keyword:
        matched = [
            row
            for row in feedbacks
            if keyword in str(row.get("question", ""))
            or keyword in str(row.get("note", ""))
            or keyword in str(row.get("library", ""))
        ]
        if not matched:
            return f"错题本里没有与「{keyword}」相关的误区记录。"
        feedbacks = matched

    # 频次归因：同一学科的误区聚合计数，帮助模型说"这类错误你出现了 N 次"。
    by_library: dict[str, int] = {}
    for row in feedbacks:
        lib = str(row.get("library") or "未分类")
        by_library[lib] = by_library.get(lib, 0) + 1

    lines = [f"共匹配到 {len(feedbacks)} 条误区记录（按学科分布："
             + "、".join(f"{lib} {count} 条" for lib, count in sorted(by_library.items()))
             + "）。"]
    for row in feedbacks[:8]:
        question = str(row.get("question") or "(未记录题目)")[:120]
        note = str(row.get("note") or "")[:160]
        lines.append(
            f"【{row.get('library') or '未分类'}】题目：{question}｜"
            f"当时记下的误区：{note}"
        )
    return "\n".join(lines)


@tool
def save_note(title: str, content: str, library: str = "日常沉淀") -> str:
    """把一段内容沉淀进某个学科知识库（会先请求用户确认）。当学生说
    "记住 / 存一下 / 沉淀 / 帮我记下"某段内容时使用。
    content 必须是一篇排版完整的 Markdown 笔记，遵守系统提示词里的
    【Markdown 笔记写作规范】：H1 标题 + 「定义/要点/例子/易错点」分节、
    每节先加粗结论、公式用 $...$ LaTeX、结尾附「自测三问」；
    不要把对话原话直接粘进来——先整理成笔记再提交确认。"""

    approved: Any = interrupt(
        {
            "action": "save_note",
            "library": library,
            "title": title,
            "preview": content[:200],
        }
    )
    if not approved:
        return "已取消，未保存。"
    get_knowledge().add_document(library, title, content)
    return f"已存入「{library}」：《{title}》"


# ---------------------------------------------------------------------------
# 联网与文件：通用 Agent 能力
# - web_search / fetch_url：联网搜索公开网页并读取正文（引用注明来源 URL）
# - write_file / read_file / list_files：学生专属的**沙箱工作区**文件读写
#   （所有路径都被限制在 data/workspace/<user_id>/ 之内，杜绝目录穿越）；
#   因为写不出去沙箱，风险可控，不做 HITL 确认。
# ---------------------------------------------------------------------------

_workspace_root: Path | None = None
READ_CHAR_LIMIT = 8000
WRITE_CHAR_LIMIT = 200_000


def get_user() -> str:
    return _current_user.get() or "local"


def configure_workspace(root: Path | str) -> None:
    """由组合根注入文件工作区根目录（每个用户在其下有独立子目录）。"""

    global _workspace_root
    _workspace_root = Path(root)


def _workspace_dir() -> Path:
    root = _workspace_root or Path("data/workspace")
    directory = root / get_user()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_resolve(filename: str) -> Path:
    """把用户给的文件名解析到工作区内；拒绝绝对路径与 .. 穿越。"""

    name = (filename or "").strip().replace("\\", "/")
    if not name:
        raise ValueError("文件名不能为空")
    if name.startswith("/") or ".." in name.split("/") or re.match(
        r"^[A-Za-z]:", name
    ):
        raise ValueError("文件名不能包含绝对路径或 .. ——文件只能放在工作区内")
    base = _workspace_dir()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError("文件只能放在工作区内")
    return candidate


_SEARCH_BACKENDS = ("auto", "duckduckgo", "brave", "mojeek", "wikipedia")


def _ddg_text(query: str, max_results: int) -> list[dict[str, Any]]:
    """DuckDuckGo 搜索（零配置兜底；独立成函数便于测试时替换）。

    单一后端在受限网络下经常整批失败：按顺序轮换多个后端，
    谁先返回非空结果就用谁。
    """

    from ddgs import DDGS

    last_error: Exception | None = None
    for backend in _SEARCH_BACKENDS:
        try:
            with DDGS() as ddgs:
                rows = list(
                    ddgs.text(query, max_results=max_results, backend=backend)
                )
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001 — 换下一个后端
            last_error = exc
            time.sleep(0.3)
    if last_error is not None:
        raise last_error
    return []


def _tavily_text(query: str, max_results: int) -> list[dict[str, Any]]:
    """Tavily 搜索（配置了 STUDYGRAPH_TAVILY_API_KEY 时优先使用，更稳定）。"""

    import httpx

    from ..config import get_settings

    api_key = get_settings().tavily_api_key
    if not api_key:
        raise RuntimeError("未配置 Tavily API Key")
    response = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=15,
    )
    response.raise_for_status()
    return [
        {
            "title": item.get("title", ""),
            "body": item.get("content", ""),
            "href": item.get("url", ""),
        }
        for item in response.json().get("results", [])
    ]


def _bing_cn_text(query: str, max_results: int) -> list[dict[str, Any]]:
    """必应中国网页搜索：国内直连稳定，结果本身就是国内可达的页面。

    抓 cn.bing.com 的搜索结果页并解析 b_algo 块；解析不出视为失败，
    让上层换下一个搜索后端。直连（trust_env=False），不绕代理节点。
    """

    import httpx

    response = httpx.get(
        "https://cn.bing.com/search",
        params={"q": query, "count": str(min(max_results * 2, 20))},
        headers=_BROWSER_HEADERS,
        timeout=15,
        follow_redirects=True,
        trust_env=False,
    )
    response.raise_for_status()
    html = response.text
    results: list[dict[str, Any]] = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, flags=re.I | re.S)[
        :max_results
    ]:
        link = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.I | re.S
        )
        if not link:
            continue
        url = link.group(1)
        title = re.sub(r"<[^>]+>", "", link.group(2))
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", block, re.I | re.S)
        snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)) if snippet_match else ""
        results.append(
            {"title": title.strip(), "body": snippet.strip()[:200], "href": url}
        )
    if not results:
        raise RuntimeError("Bing 未解析出结果（页面结构可能变化）")
    return results


def _search_web(query: str, max_results: int) -> list[dict[str, Any]]:
    """搜索调度：Tavily（配了 Key）→ 必应中国（国内直连最稳）→ DuckDuckGo。"""

    errors: list[str] = []
    try:
        from ..config import get_settings

        if get_settings().tavily_api_key:
            try:
                return _tavily_text(query, max_results)
            except Exception as exc:  # noqa: BLE001 — 换下一个后端
                errors.append(f"tavily: {exc}")
    except Exception:  # noqa: BLE001 — 读配置失败忽略
        pass
    try:
        return _bing_cn_text(query, max_results)
    except Exception as exc:  # noqa: BLE001 — 换下一个后端
        errors.append(f"bing: {exc}")
    try:
        return _ddg_text(query, max_results)
    except Exception as exc:  # noqa: BLE001 — 最后一个后端
        errors.append(f"ddg: {exc}")
    raise RuntimeError("；".join(errors) or "没有可用搜索后端")


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """联网搜索：在公开网页上查找资料，返回标题、摘要和链接。当需要
    最新信息、通用知识、范文模板，或知识库里没有相关内容时使用；
    引用搜索结果时要注明来源 URL。"""
    query = (query or "").strip()
    if not query:
        return "联网搜索失败：查询词为空。"
    try:
        max_results = max(1, min(int(max_results or 5), 10))
        # 搜索后端偶发瞬时网络错误：原地重试一次（错误转可读提示，不炸回合）
        results: list[dict[str, Any]] = []
        for attempt in range(2):
            try:
                results = _search_web(query, max_results)
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(0.8)
    except Exception as exc:  # noqa: BLE001 — 网络故障转成可读提示，不炸回合
        return (
            f"联网搜索失败：{type(exc).__name__} {exc}。"
            "可以先基于已有资料回答，并说明未能联网核实。"
        )
    if not results:
        return f"没有搜索到与「{query}」相关的结果。"
    lines = [f"共 {len(results)} 条结果："]
    for item in results:
        title = str(item.get("title") or "").strip()[:80]
        snippet = str(item.get("body") or item.get("snippet") or "").strip()[:160]
        url = str(item.get("href") or item.get("url") or "").strip()
        lines.append(f"【{title}】{snippet}（{url}）")
    return "\n".join(lines)


def _assert_public_url(url: str) -> None:
    """SSRF 防护：只允许 http/https 公网地址，拒绝内网 / 本机目标。"""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("只支持 http/https 链接")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("链接缺少主机名")
    blocked_prefixes = ("127.", "10.", "192.168.", "169.254.", "0.")
    if (
        host in ("localhost", "[::1]", "::1")
        or host.endswith(".local")
        or host.startswith(blocked_prefixes)
        or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host)
    ):
        raise ValueError("不允许访问内网或本机地址")


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _fetch_attempt(url: str, *, use_env_proxy: bool) -> str:
    """按一种网络策略抓取网页（trust_env 决定是否走系统代理）。"""

    import html as html_lib

    import httpx

    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        trust_env=use_env_proxy,
        headers=_BROWSER_HEADERS,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.startswith(
            ("text/", "application/json")
        ):
            raise ValueError(f"不支持的内容类型：{content_type.split(';')[0]}")
        html = response.text

    html = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    html = re.sub(r"<(br|/p|/div|/h[1-6]|/li|/tr)[^>]*>", "\n", html, flags=re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", html))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _fetch_page_text(url: str) -> str:
    """多策略抓取：直连 → 代理 → 再直连。

    国内站点直连最快最稳（代理节点反而在国外）；国外站点直连被重置时
    由代理策略兜底。三种策略轮着试，谁成功用谁；全失败才抛给上层。
    """

    attempts = (
        {"use_env_proxy": False},
        {"use_env_proxy": True},
        {"use_env_proxy": False},
    )
    last_error: Exception | None = None
    for attempt in attempts:
        try:
            text = _fetch_attempt(url, **attempt)
            if text:
                return text
            last_error = ValueError("网页内容为空")
        except Exception as exc:  # noqa: BLE001 — 记住最后一个错误，换下一策略
            last_error = exc
            time.sleep(0.4)
    assert last_error is not None
    raise last_error


@tool
def fetch_url(url: str) -> str:
    """读取一个网页的正文文本（自动去掉标签与脚本）。配合联网搜索使用：
    先 web_search 拿到链接，再用它读取具体页面。只支持 http/https 公网地址。"""
    url = (url or "").strip()
    try:
        _assert_public_url(url)
        text = _fetch_page_text(url)
    except Exception as exc:  # noqa: BLE001 — 失败转可读提示
        return f"读取网页失败：{exc}"
    if not text:
        return "网页内容为空（可能是纯脚本渲染的页面，换个来源试试）。"
    host = urllib.parse.urlparse(url).netloc
    note = (
        f"\n\n（内容过长，已截断到前 {READ_CHAR_LIMIT} 字）"
        if len(text) > READ_CHAR_LIMIT
        else ""
    )
    return f"读取成功：{host}（共约 {len(text)} 字）\n\n{text[:READ_CHAR_LIMIT]}{note}"


@tool
def write_file(filename: str, content: str) -> str:
    """把内容写进学生的文件工作区（Markdown / 文本 / 代码等，同名会覆盖）。
    用于保存整理结果、生成模板、写学习计划草稿等；之后可以用 read_file
    读回、list_files 查看。文件只能放在工作区内，不能写系统其他位置。"""
    try:
        path = _safe_resolve(filename)
    except ValueError as exc:
        return f"写入失败：{exc}"
    content = content or ""
    if len(content) > WRITE_CHAR_LIMIT:
        return f"写入失败：内容超过 {WRITE_CHAR_LIMIT} 字上限"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    rel = path.relative_to(_workspace_dir())
    return f"已写入工作区：{rel}（{len(content)} 字）"


@tool
def read_file(filename: str) -> str:
    """读取工作区里一个文本文件的内容（Markdown / 文本 / 代码等）。
    当学生问"我之前让你存的东西"、或需要先读文件再修改时使用。"""
    try:
        path = _safe_resolve(filename)
    except ValueError as exc:
        return f"读取失败：{exc}"
    if not path.exists() or not path.is_file():
        return f"读取失败：工作区里没有「{filename}」。可以用 list_files 先看看有哪些文件。"
    raw = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(_workspace_dir())
    note = (
        f"\n\n（文件共 {len(raw)} 字，已截断到前 {READ_CHAR_LIMIT} 字）"
        if len(raw) > READ_CHAR_LIMIT
        else ""
    )
    return f"读取成功：{rel}（{len(raw)} 字）\n\n{raw[:READ_CHAR_LIMIT]}{note}"


@tool
def list_files() -> str:
    """列出学生文件工作区里的所有文件（按最近修改排序）。当需要确认
    工作区里有什么、或用户提到的文件名不确定时先调这个。"""
    directory = _workspace_dir()
    files = [item for item in directory.rglob("*") if item.is_file()]
    if not files:
        return "工作区还是空的。"
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    lines = [f"共 {len(files)} 个文件："]
    for item in files[:50]:
        rel = item.relative_to(directory)
        lines.append(f"- {rel}（{item.stat().st_size} 字节）")
    if len(files) > 50:
        lines.append(f"…（还有 {len(files) - 50} 个未列出）")
    return "\n".join(lines)


TOOLS = {
    "calculator": calculator,
    "knowledge_search": knowledge_search,
    "mistake_search": mistake_search,
    "save_note": save_note,
    "web_search": web_search,
    "fetch_url": fetch_url,
    "write_file": write_file,
    "read_file": read_file,
    "list_files": list_files,
}

# 通过 MCP 动态注册进来的工具名（前缀 mcp_）。
_mcp_names: set[str] = set()


def get_tool(name: str):
    return TOOLS.get(name)


def is_mcp_tool(name: str) -> bool:
    """判断一个工具名是不是 MCP 外部工具（执行层权限判定用）。"""

    return name in _mcp_names


def register_mcp_tool(name: str, tool: Any) -> None:
    TOOLS[name] = tool
    _mcp_names.add(name)


def mcp_tool_names() -> list[str]:
    return sorted(_mcp_names)
