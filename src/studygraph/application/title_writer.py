"""聊天自动起标题——应用层小服务。

新会话落库时标题还是「新对话」，首轮回复结束后用模型把首条消息
压缩成一句短标题。设计原则：
- **标题是锦上添花，不是关键路径**：任何失败（模型为空、超时、输出
  不合格）都静默降级为「首条消息截断」，绝不让发消息这件事失败；
- 输出必须干净：去引号、去前缀，超过 20 字视为不合格走降级。
"""

from __future__ import annotations

import re

MAX_TITLE_LEN = 20
FALLBACK_LEN = 12
_FALLBACK = "新对话"

_PREFIXES = ("标题：", "标题:", "## ", "# ", "- ", "* ")
_NOISE = re.compile(r"[\n\r]+|[\"'「」『』《》]")


def _fallback_title(text: str) -> str:
    cleaned = _NOISE.sub(" ", text).strip()
    return (cleaned[:FALLBACK_LEN] + "…") if len(cleaned) > FALLBACK_LEN else (
        cleaned or _FALLBACK
    )


def _clean_title(text: str) -> str:
    title = str(getattr(text, "content", text) or "").strip()
    for prefix in _PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
    title = _NOISE.sub(" ", title).strip()
    # 句号/逗号结尾的"半句话感"去掉，标题不需要标点收尾。
    return title.rstrip("。，,;；.！!？?")


async def generate_title(model, first_message: str) -> str:
    """把首条用户消息压缩成 ≤20 字的会话标题；失败时降级截断。"""

    snippet = " ".join(first_message.split())[:200].strip()
    if not snippet:
        return _FALLBACK
    if model is None:
        return _fallback_title(snippet)

    prompt = (
        "给下面这段学习对话的开头起一个简短标题：只输出标题本身，"
        f"不要引号、不要句号、不要任何解释，最多 {MAX_TITLE_LEN} 个字。\n\n"
        f"对话开头：{snippet}"
    )
    try:
        response = await model.ainvoke(prompt)
    except Exception:  # noqa: BLE001 — 标题失败不该影响聊天
        return _fallback_title(snippet)
    title = _clean_title(response)
    if not title or len(title) > MAX_TITLE_LEN:
        return _fallback_title(snippet)
    return title
