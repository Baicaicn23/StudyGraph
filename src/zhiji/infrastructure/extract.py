"""从上传文件里抽取文本（TXT / Markdown / PDF / Word / PPT / Excel）；图片交给视觉模型转写。

抽取尽量**按页拆分**：PDF 按物理页（pypdf），PPTX 按 slide（markitdown 的
`<!-- Slide number: N -->` 标记）；其余格式整篇一块、无页码标签。页码标签供
检索切块时带出处（如「【第 3 页】」），AI 引文能落到具体页。

Word/PPT/Excel 走 markitdown（微软 MIT；DOCX=mammoth、PPTX=python-pptx、
XLSX=openpyxl）。老格式 .doc / .ppt 不支持解析——原件照常落盘可下载。
"""

from __future__ import annotations

import io
import re

_TEXT_SUFFIXES = (".txt", ".md", ".markdown")
# 视觉模型支持的图片格式（转 Markdown 入库，见 application/image_notes.py）。
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

# markitdown 能抽文本的格式（.doc/.ppt 老二进制格式不支持，只能下载原文）。
_MARKITDOWN_SUFFIXES = (".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm", ".csv")
# 懒解析支持的范围 = PDF + markitdown 可处理格式。
PARSE_SUFFIXES = (".pdf",) + _MARKITDOWN_SUFFIXES

# markitdown 的 PPTX 输出按 slide 打标记：<!-- Slide number: 12 -->
_SLIDE_MARKER = re.compile(r"<!--\s*Slide number:\s*(\d+)\s*-->")

# OOXML 家族是 zip 容器（PK）、老 .xls 是 OLE2 容器；markitdown 对解析失败的
# 文件会兜底按纯文本读，必须先用魔数挡掉损坏/伪装文件，避免把垃圾索引进库。
_MAGIC_CHECKS: tuple[tuple[str, bytes], ...] = (
    (".docx", b"PK\x03\x04"),
    (".pptx", b"PK\x03\x04"),
    (".xlsx", b"PK\x03\x04"),
    (".xls", b"\xd0\xcf\x11\xe0"),
)


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


def is_parseable_document(filename: str) -> bool:
    """该格式是否支持懒解析（建立检索索引）。"""

    name = (filename or "").lower()
    return name.endswith(PARSE_SUFFIXES)


def extract_pages(filename: str, data: bytes) -> list[tuple[str | None, str]]:
    """抽取文本并尽量按页拆分，返回 (页码标签, 页文本) 列表。

    标签形如「第 3 页」；无法分页的格式（TXT / Word 等）返回单页、标签为 None。
    全文无文本时返回空列表（调用方据此提示"可能是扫描件"）。
    """

    name = (filename or "").lower()
    if name.endswith(_TEXT_SUFFIXES):
        text = data.decode("utf-8", errors="ignore").strip()
        return [(None, text)] if text else []
    if name.endswith(".pdf"):
        return _pdf_pages(data)
    if name.endswith(_MARKITDOWN_SUFFIXES):
        return _markitdown_pages(name, data)
    raise ExtractError("暂只支持 TXT / Markdown / PDF / Word / PPT / Excel / 图片文件")


def extract_text(filename: str, data: bytes) -> str:
    """整篇文本（不带页码标签）——聊天附件等不需要出处的场景用。"""

    return "\n\n".join(text for _label, text in extract_pages(filename, data)).strip()


def _pdf_pages(data: bytes) -> list[tuple[str | None, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的清晰提示
        raise ExtractError("解析 PDF 需要 pypdf，请执行 `uv sync`") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages: list[tuple[str | None, str]] = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((f"第 {number} 页", text))
    except ExtractError:
        raise
    except Exception as exc:  # noqa: BLE001 - 把底层异常转成可读错误
        raise ExtractError(f"PDF 解析失败：{exc}") from exc
    return pages


def _markitdown_pages(name: str, data: bytes) -> list[tuple[str | None, str]]:
    for suffix, magic in _MAGIC_CHECKS:
        if name.endswith(suffix) and not data.startswith(magic):
            raise ExtractError("不是有效的 Word / PPT / Excel 文件（文件可能已损坏）")
    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的清晰提示
        raise ExtractError("解析 Word / PPT / Excel 需要 markitdown，请执行 `uv sync`") from exc
    suffix = name[name.rindex("."):]
    try:
        result = MarkItDown().convert_stream(io.BytesIO(data), file_extension=suffix)
        text = (result.text_content or "").strip()
    except Exception as exc:  # noqa: BLE001 - 把底层异常转成可读错误
        raise ExtractError(f"文档解析失败：{exc}") from exc
    if not text:
        return []
    markers = list(_SLIDE_MARKER.finditer(text))
    if not markers:  # Word / Excel / 网页等没有页标记，整篇一块
        return [(None, text)]
    pages: list[tuple[str | None, str]] = []
    head = text[: markers[0].start()].strip()
    if head:
        pages.append((None, head))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[marker.end():end].strip()
        if body:
            pages.append((f"第 {marker.group(1)} 页", body))
    return pages
