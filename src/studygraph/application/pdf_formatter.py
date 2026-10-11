"""PDF 智能格式化：把 pypdf 抽出的平铺文本重排成结构化 Markdown。

pypdf 只能抽出"流"文本——章节层级、题号、列表、表格全部丢失，
阅读器里就是一坨挤在一起的段落。这里用模型做**忠实重排**：

- 只修版式，不改内容：不增删改任何知识点，数字、术语、原文措辞原样保留；
- 结构还原：章节标题升级为标题层级、题号保留、并列内容列表化、公式 LaTeX 化；
- 分块处理长 PDF（按行边界切块，每块独立重排，拼接时保留顺序）；
- Mock / None 模型 → 原样返回（与旧行为一致，不消耗额度）；
- 单块失败不炸整体：失败的块保留原文。
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from .ports import ChatModelPort

_CHUNK_CHARS = 3000
_MAX_FORMATTED_CHARS = 60_000

_SYSTEM_PROMPT = (
    "你是 PDF 版式整理员。把 pypdf 从 PDF 里抽出的**平铺文本**重排成结构化 "
    "Markdown。这是忠实转换，不是改写：\n"
    "一、内容纪律：不增删改任何知识点——数字、术语、专有名词、原文措辞原样保留；\n"
    "看不出来是正文还是页眉页脚的行，宁可保留；\n"
    "二、结构还原：章节/课名/作业名升级为「## 标题」，小节用「###」；题号"
    "（1. 2. （1）①）保留并列表化；并列内容用列表；对比内容用表格；\n"
    "三、排版：数学式用 $...$ LaTeX；去掉页码、页眉页脚、多余空行；\n"
    "四、只输出重排后的 Markdown，不要解释，不要代码块包裹。\n"
    "分块处理时：块边界可能切断句子，只整理本块内的完整内容，不要补写。"
)


def _chunk_text(text: str, chunk_chars: int = _CHUNK_CHARS) -> list[str]:
    """按行边界切块（不切断行），控制在 chunk_chars 上下。"""

    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1
        if current_len + line_len > chunk_chars and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def _clean_formatted(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n?", "", text, flags=re.M)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def format_pdf_markdown(
    model: ChatModelPort | None,
    *,
    raw_text: str,
) -> str:
    """把 PDF 抽取文本重排为结构化 Markdown（忠实转换，分块处理）。

    Mock / None 模型 → 原样返回；单块失败保留该块原文，不炸整体。
    """

    raw = (raw_text or "").strip()
    if not raw:
        return raw
    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return raw

    chunks = _chunk_text(raw[:_MAX_FORMATTED_CHARS])
    formatted: list[str] = []
    for chunk in chunks:
        try:
            response = await model.ainvoke(
                [
                    SystemMessage(_SYSTEM_PROMPT),
                    HumanMessage(f"【PDF 抽取文本 · {len(chunk)} 字】\n\n{chunk}"),
                ]
            )
            cleaned = _clean_formatted(str(getattr(response, "content", "")))
            formatted.append(cleaned if cleaned else chunk)
        except Exception:  # noqa: BLE001 — 单块失败保留原文
            formatted.append(chunk)

    return "\n\n".join(formatted)[:_MAX_FORMATTED_CHARS]
