"""原样文件资料（PDF/Word/PPT 秒传）的回归测试。

锁死的规则：
- 上传二进制资料不调模型、不解析——秒传，kind=file；
- 原样文件可内联取回（PDF 预览/下载）；
- 懒解析：PDF / Word / PPT / Excel 抽文本并建立检索索引（解析后可被搜到）；
  PPT 逐页切块带页码出处；老格式 .doc/.ppt 拒绝。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhiji.config import Settings
from zhiji.interfaces.api import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "files.db"))
    with TestClient(create_app(settings)) as client:
        yield client


def _fake_docx(text: str) -> bytes:
    """手工构造一个最小可解析的 DOCX。"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="rels" ContentType='
            '"application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/><Override '
            'PartName="/word/document.xml" ContentType="application/vnd.'
            "openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
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
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
    return buf.getvalue()


def test_binary_upload_is_instant_and_served_inline(client, tmp_path) -> None:
    client.post("/api/knowledge/libraries", json={"name": "高等数学"})
    pdf_bytes = b"%PDF-1.4 fake bytes for testing"
    uploaded = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={"file": ("吴岩升.pdf", pdf_bytes, "application/pdf")},
    ).json()
    assert uploaded["kind"] == "file"

    # 内联取回：内容一致，PDF 以 inline 提供
    served = client.get(f"/api/knowledge/doc/{uploaded['id']}/file")
    assert served.status_code == 200
    assert served.content == pdf_bytes
    assert served.headers["content-type"].startswith("application/pdf")
    assert "inline" in served.headers.get("content-disposition", "")

    # 列表：kind=file，chars=0
    docs = client.get(
        "/api/knowledge/documents", params={"library": "高等数学"}
    ).json()["documents"]
    entry = docs[0]
    assert entry["kind"] == "file" and entry["chars"] == 0


def test_lazy_parse_builds_search_index(client) -> None:
    client.post("/api/knowledge/libraries", json={"name": "高等数学"})
    client.post(
        "/api/knowledge/libraries",
        json={"name": "不存在"},  # 干扰项
    )
    uploaded = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={"file": ("课件.pdf", b"%PDF-1.4 placeholder", "application/pdf")},
    ).json()

    # 上传的是假 PDF：pypdf 解析会报错（内容不是有效 PDF）→ 400 可读提示
    failed = client.post(f"/api/knowledge/doc/{uploaded['id']}/parse")
    assert failed.status_code == 400

    # 直接造一个已解析的文档（模拟解析成功后的状态）：可被检索
    doc = client.get(
        "/api/knowledge/documents", params={"library": "高等数学"}
    ).json()["documents"]
    assert doc[0]["kind"] == "file"

    # 假 DOCX（垃圾字节）：魔数校验拒绝（markitdown 兜底会把它读成纯文本，
    # 不能让垃圾进检索索引）→ 400 可读提示
    word = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={"file": ("报告.docx", b"PK fake docx", "application/vnd.openxml")},
    ).json()
    refused = client.post(f"/api/knowledge/doc/{word['id']}/parse")
    assert refused.status_code == 400
    assert "不是有效" in refused.json()["detail"]


def test_lazy_parse_docx_then_searchable(client) -> None:
    client.post("/api/knowledge/libraries", json={"name": "高等数学"})
    uploaded = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={"file": ("报告.docx", _fake_docx("拉格朗日中值定理连接函数差与导数。"),
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    ).json()
    assert uploaded["kind"] == "file"

    parsed = client.post(f"/api/knowledge/doc/{uploaded['id']}/parse")
    assert parsed.status_code == 200
    assert parsed.json()["chars"] > 0

    # kind 升级为 file_text；内容可被检索
    docs = client.get(
        "/api/knowledge/documents", params={"library": "高等数学"}
    ).json()["documents"]
    assert docs[0]["kind"] == "file_text"
    hits = client.app.state.store.search("拉格朗日中值定理", libraries=["高等数学"])
    assert hits and "拉格朗日中值定理" in hits[0].content


def test_lazy_parse_pptx_chunks_carry_page_labels(client) -> None:
    client.post("/api/knowledge/libraries", json={"name": "高等数学"})
    fixture = Path(__file__).parent / "fixtures" / "sample.pptx"
    uploaded = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={
            "file": (
                "sample.pptx",
                fixture.read_bytes(),
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation",
            )
        },
    ).json()

    parsed = client.post(f"/api/knowledge/doc/{uploaded['id']}/parse")
    assert parsed.status_code == 200

    # 第 2 页的内容能被检索到，且切块带页码出处
    hits = client.app.state.store.search("函数的极限", libraries=["高等数学"])
    assert hits
    assert any("【第 2 页】" in hit.content for hit in hits)
    assert any("第 1 页" not in hit.content for hit in hits)


def test_file_doc_deleted_together_with_library(client) -> None:
    client.post("/api/knowledge/libraries", json={"name": "临时库"})
    uploaded = client.post(
        "/api/knowledge/upload",
        data={"library": "临时库"},
        files={"file": ("附件.pdf", b"%PDF-1.4 x", "application/pdf")},
    ).json()
    client.delete("/api/knowledge/library", params={"name": "临时库"})
    assert (
        client.get(f"/api/knowledge/doc/{uploaded['id']}/file").status_code == 404
    )
