"""从上传文件里抽取纯文本（TXT / Markdown / PDF）。

只做"把文件变成字符串"这一件事；切块、索引、向量化交给 `KnowledgeStore`。
PDF 用可选的 `pypdf`（已在主依赖里）；未知后缀直接报错，不猜测格式。
"""

from __future__ import annotations

import io

_TEXT_SUFFIXES = (".txt", ".md", ".markdown")
_SUPPORTED = _TEXT_SUFFIXES + (".pdf",)


class ExtractError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(_TEXT_SUFFIXES):
        return data.decode("utf-8", errors="ignore").strip()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    raise ExtractError("暂只支持 TXT / Markdown / PDF 文件")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的清晰提示
        raise ExtractError("解析 PDF 需要 pypdf，请执行 `uv sync`") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - 把底层异常转成可读错误
        raise ExtractError(f"PDF 解析失败：{exc}") from exc
    return "\n\n".join(pages).strip()
