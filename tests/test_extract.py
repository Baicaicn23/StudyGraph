from __future__ import annotations

import pytest

from studygraph.infrastructure.extract import (
    ExtractError,
    extract_text,
    image_mime,
    is_image,
)


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
