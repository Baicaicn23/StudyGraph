"""Agent 可调用的工具。

三个内置工具：
- `calculator`：安全算术求值，杜绝直接 eval 注入。
- `knowledge_search`：在学科知识库里检索，返回带出处的片段。
- `save_note`：把内容沉淀进某个学科库——**会先 `interrupt()` 请求用户确认**
  （Human-in-the-Loop），确认后才落库。

工具依赖的是**端口**（`KnowledgePort`），不是具体实现；"本轮选中的知识库"用
contextvar 传递，避免污染模型可见的参数 schema。
"""

from __future__ import annotations

import ast
import contextvars
import operator
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt

from .ports import KnowledgePort

_knowledge: KnowledgePort | None = None
_current_libraries: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "studygraph_current_libraries", default=None
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


def configure(knowledge: KnowledgePort) -> None:
    """由组合根注入知识库实现。"""

    global _knowledge
    _knowledge = knowledge


def get_knowledge() -> KnowledgePort:
    if _knowledge is None:
        raise RuntimeError("工具尚未配置知识库：请先调用 tools.configure(...)")
    return _knowledge


def set_current_libraries(libraries: list[str] | None) -> None:
    _current_libraries.set(list(libraries) if libraries else None)


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
        return "知识库里没有找到相关片段。"
    blocks = [f"【{hit.library} / {hit.title}】{hit.content}" for hit in hits]
    return "\n\n".join(blocks)


@tool
def save_note(title: str, content: str, library: str = "日常沉淀") -> str:
    """把一段内容沉淀进某个学科知识库（会先请求用户确认）。当学生说
    "记住 / 存一下 / 沉淀 / 帮我记下"某段内容时使用。"""

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


TOOLS = {
    "calculator": calculator,
    "knowledge_search": knowledge_search,
    "save_note": save_note,
}

# 通过 MCP 动态注册进来的工具名（前缀 mcp_）。
_mcp_names: set[str] = set()


def get_tool(name: str):
    return TOOLS.get(name)


def register_mcp_tool(name: str, tool: Any) -> None:
    TOOLS[name] = tool
    _mcp_names.add(name)


def mcp_tool_names() -> list[str]:
    return sorted(_mcp_names)
