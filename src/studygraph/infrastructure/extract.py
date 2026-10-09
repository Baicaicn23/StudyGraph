"""从上传文件里抽取纯文本（TXT / Markdown / PDF）；图片交给视觉模型转写。"""

from __future__ import annotations

import io

_TEXT_SUFFIXES = (".txt", ".md", ".markdown")
# 视觉模型支持的图片格式（转 Markdown 入库，见 application/image_notes.py）。
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class ExtractError(ValueError):
    pass


def is_image(filename: str) -> bool:
    name = (filename or "").lower()
    return name.endswith(_IMAGE_SUFFIXES)


def image_mime(filename: str) -> str | None:
    name = (filename or "").lower()
    for suffix, mime in _IMAGE_MIME.items():
        if name.endswith(suffix):
            return mime
    return None


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(_TEXT_SUFFIXES):
        return data.decode("utf-8", errors="ignore").strip()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    raise ExtractError("暂只支持 TXT / Markdown / PDF / 图片文件")


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
