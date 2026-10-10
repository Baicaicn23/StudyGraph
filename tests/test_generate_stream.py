"""流式出题进度（/api/practice/generate/stream）的回归测试。

锁死事件协议：每出一题一帧 progress（done/total/library/difficulty），
收尾一帧 done 带 questions 全量；LearningError 转为 error 帧。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "genstream.db"))
    return TestClient(create_app(settings))


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = line[len("data: "):]
        if event and data:
            import json

            events.append((event, json.loads(data)))
    return events


def test_stream_emits_progress_then_done(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/api/knowledge/notes",
            json={
                "library": "高等数学",
                "title": "导数笔记",
                "content": "导数是瞬时变化率。微分是线性主部。泰勒展开是近似工具。",
            },
        )
        response = client.post(
            "/api/practice/generate/stream",
            json={"source": "knowledge_base", "library": "高等数学", "count": 3},
        )
        assert response.status_code == 200
        events = _parse_sse(response.text)

        progresses = [data for name, data in events if name == "progress"]
        dones = [data for name, data in events if name == "done"]
        # 出题受知识库切片数限制：实际生成 n 题 → progress 恰好 n 帧、逐帧递增
        produced = len(dones[0]["questions"])
        assert produced >= 1
        assert [item["done"] for item in progresses] == list(
            range(1, produced + 1)
        )
        assert all(item["total"] == produced for item in progresses)
        assert progresses[0]["library"] == "高等数学"
        assert len(dones) == 1


def test_stream_learing_error_becomes_error_event(tmp_path) -> None:
    with _client(tmp_path) as client:
        # 不存在的知识库 → 400 逻辑错误转成 SSE error 帧（而非 HTTP 状态码）
        response = client.post(
            "/api/practice/generate/stream",
            json={"source": "knowledge_base", "library": "不存在的库", "count": 1},
        )
        assert response.status_code == 200
        events = _parse_sse(response.text)
        errors = [data for name, data in events if name == "error"]
        assert len(errors) == 1
        assert "知识库" in errors[0]["message"]
