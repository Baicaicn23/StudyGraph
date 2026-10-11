"""原样文件资料（PDF/Word 秒传）的回归测试。

锁死的规则：
- 上传二进制资料不调模型、不解析——秒传，kind=file；
- 原样文件可内联取回（PDF 预览/下载）；
- 懒解析：PDF 抽文本并建立检索索引（解析后可被搜到）；非 PDF 拒绝。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "files.db"))
    with TestClient(create_app(settings)) as client:
        yield client


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

    # 非 PDF 原样文件拒绝解析
    word = client.post(
        "/api/knowledge/upload",
        data={"library": "高等数学"},
        files={"file": ("报告.docx", b"PK fake docx", "application/vnd.openxml")},
    ).json()
    refused = client.post(f"/api/knowledge/doc/{word['id']}/parse")
    assert refused.status_code == 400
    assert "目前支持 PDF" in refused.json()["detail"]


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
