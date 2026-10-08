from __future__ import annotations

import pytest

from studygraph.infrastructure.extract import ExtractError, extract_text


def test_extract_plain_text_and_markdown() -> None:
    assert extract_text("note.txt", "导数是瞬时变化率".encode()) == "导数是瞬时变化率"
    assert extract_text("note.md", "# 标题\n\n正文".encode()) == "# 标题\n\n正文"


def test_extract_rejects_unsupported_suffix() -> None:
    with pytest.raises(ExtractError):
        extract_text("image.png", b"\x89PNG")


def test_extract_pdf_reports_error_on_garbage() -> None:
    with pytest.raises(ExtractError):
        extract_text("broken.pdf", b"not a real pdf")
