from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from zhiji.infrastructure.extract import (
    ExtractError,
    extract_pages,
    extract_text,
    image_mime,
    is_image,
    is_parseable_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_docx(paragraphs: list[str]) -> bytes:
    """手工构造一个最小可解析的 DOCX（mammoth 只认 OOXML 三件套）。"""

    buf = io.BytesIO()
    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="rels" ContentType='
            '"application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/><Override '
            'PartName="/word/document.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
            "openxmlformats.org/package/2006/relationships\"><Relationship "
            'Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
            'openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + body
            + "</w:body></w:document>",
        )
    return buf.getvalue()


def test_extract_plain_text_and_markdown() -> None:
    assert extract_text("note.txt", "导数是瞬时变化率".encode()) == "导数是瞬时变化率"
    assert extract_text("note.md", "# 标题\n\n正文".encode()) == "# 标题\n\n正文"


def test_extract_rejects_unsupported_suffix() -> None:
    # 图片不在 extract_text 的职责内——它们走视觉模型转写（application/image_notes）。
    with pytest.raises(ExtractError):
        extract_text("image.png", b"\x89PNG")


def test_extract_pdf_reports_error_on_garbage() -> None:
    with pytest.raises(ExtractError):
        extract_text("broken.pdf", b"not a real pdf")


def test_image_detection_and_mime() -> None:
    assert is_image("板书.PNG")
    assert is_image("photo.JPG")
    assert is_image("slide.webp")
    assert not is_image("notes.pdf")
    assert not is_image("readme.md")
    assert image_mime("板书.jpg") == "image/jpeg"
    assert image_mime("slide.png") == "image/png"
    assert image_mime("notes.pdf") is None


def test_extract_pages_splits_pptx_by_slide() -> None:
    pages = extract_pages("sample.pptx", (FIXTURES / "sample.pptx").read_bytes())
    assert [label for label, _ in pages] == ["第 1 页", "第 2 页"]
    assert "集合的概念" in pages[0][1]
    assert "函数的极限" in pages[1][1]


def test_extract_docx_single_page_without_label() -> None:
    data = _fake_docx(["导数的几何意义是切线斜率。"])
    pages = extract_pages("报告.docx", data)
    assert pages == [(None, "导数的几何意义是切线斜率。")]
    assert extract_text("报告.docx", data) == "导数的几何意义是切线斜率。"


def test_extract_pages_empty_text_returns_empty_list() -> None:
    assert extract_pages("空白.docx", _fake_docx([])) == []


def test_legacy_doc_ppt_not_parseable() -> None:
    assert not is_parseable_document("老课件.doc")
    assert not is_parseable_document("老课件.ppt")
    assert is_parseable_document("课件.pdf")
    assert is_parseable_document("报告.docx")
    assert is_parseable_document("课件.pptx")
    assert is_parseable_document("表格.xlsx")
    with pytest.raises(ExtractError):
        extract_text("老课件.doc", b"legacy bytes")


def test_corrupt_ooxml_rejected_by_magic_check() -> None:
    # markitdown 解析失败会兜底按纯文本读，魔数校验必须先把损坏文件挡掉
    with pytest.raises(ExtractError, match="不是有效"):
        extract_pages("伪装.docx", b"PK fake docx")
    with pytest.raises(ExtractError, match="不是有效"):
        extract_pages("伪装.pptx", b"not a zip at all")
