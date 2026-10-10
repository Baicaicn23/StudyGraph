"""联网与文件工具的回归测试（全部离线：搜索与抓取都替换成桩）。

锁死的规则：
- 文件工具只能落在工作区内（绝对路径 / .. / 反斜杠穿越都拒绝）；
- web_search 结果格式稳定，网络故障转成可读提示而不是抛异常；
- fetch_url 只允许 http/https 公网地址（SSRF 防护），结果带元信息首行；
- 权限：tutor / retriever / chat 拿到对应的新工具，practice / progress 拿不到。
"""

from __future__ import annotations

import pytest

from studygraph.application import tools
from studygraph.application.routing import allowed_tools, profile_for_agent
from studygraph.config import Settings
from studygraph.interfaces.api import create_app


@pytest.fixture()
def workspace(tmp_path):
    """配置临时工作区 + 用户 u，并在测试后恢复全局状态（contextvar 会跨测试泄漏）。"""

    old_root = tools._workspace_root
    user_token = tools._current_user.set("u")
    tools.configure_workspace(tmp_path / "workspace")
    yield tmp_path / "workspace" / "u"
    tools._current_user.reset(user_token)
    tools._workspace_root = old_root


def test_file_roundtrip_and_listing(workspace) -> None:
    written = tools.write_file.invoke(
        {"filename": "notes/作文模板.md", "content": "# 模板\n正文"}
    )
    assert "已写入" in written and "notes/作文模板.md" in written

    read = tools.read_file.invoke({"filename": "notes/作文模板.md"})
    assert "读取成功" in read and "# 模板" in read

    listing = tools.list_files.invoke({})
    assert "notes/作文模板.md" in listing and "1 个文件" in listing

    # 覆盖写
    tools.write_file.invoke({"filename": "notes/作文模板.md", "content": "v2"})
    assert "v2" in tools.read_file.invoke({"filename": "notes/作文模板.md"})


def test_filename_traversal_blocked(workspace) -> None:
    for bad in ["../evil.txt", "/etc/passwd", "a/../../b.txt", "C:\\x.txt"]:
        out = tools.write_file.invoke({"filename": bad, "content": "x"})
        assert out.startswith("写入失败"), f"{bad} 应被拒绝"
    assert tools.read_file.invoke({"filename": "../../secret"}).startswith("读取失败")
    # 工作区之外没有任何文件被写出来
    assert not (workspace.parent.parent / "evil.txt").exists()


def test_read_missing_file_is_readable_error(workspace) -> None:
    out = tools.read_file.invoke({"filename": "不存在.md"})
    assert out.startswith("读取失败")
    assert "list_files" in out  # 告诉模型下一步怎么办


def test_web_search_formats_and_degrades(workspace, monkeypatch) -> None:
    monkeypatch.setattr(
        tools,
        "_ddg_text",
        lambda q, n: [
            {
                "title": "六级作文模板",
                "body": "三段式议论文章法",
                "href": "https://example.com/a",
            }
        ],
    )
    out = tools.web_search.invoke({"query": "英语六级作文模板"})
    assert out.startswith("共 1 条结果：")
    assert "【六级作文模板】" in out and "https://example.com/a" in out

    def boom(query, max_results):
        raise RuntimeError("network down")

    monkeypatch.setattr(tools, "_ddg_text", boom)
    degraded = tools.web_search.invoke({"query": "x"})
    assert degraded.startswith("联网搜索失败：") and "network down" in degraded

    assert tools.web_search.invoke({"query": ""}).startswith("联网搜索失败")


def test_fetch_url_guard_and_format(workspace, monkeypatch) -> None:
    for bad in [
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://192.168.1.2/x",
        "http://169.254.1.1/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ]:
        assert tools.fetch_url.invoke({"url": bad}).startswith("读取网页失败"), bad

    monkeypatch.setattr(tools, "_fetch_page_text", lambda url: "正文第一行\n正文第二行")
    out = tools.fetch_url.invoke({"url": "https://example.com/page"})
    assert out.startswith("读取成功：example.com")
    assert "正文第一行" in out

    # 非文本内容类型被拒
    def binary(url):
        raise ValueError("不支持的内容类型：image/png")

    monkeypatch.setattr(tools, "_fetch_page_text", binary)
    assert tools.fetch_url.invoke({"url": "https://example.com/a.png"}).startswith(
        "读取网页失败"
    )


def test_profiles_get_new_tools() -> None:
    tutor = allowed_tools(profile_for_agent("tutor"), None)
    assert {"web_search", "fetch_url", "write_file", "read_file", "list_files"} <= set(
        tutor
    )

    retriever = allowed_tools(profile_for_agent("retriever"), None)
    assert {
        "web_search",
        "fetch_url",
        "write_file",
        "read_file",
        "list_files",
    } <= set(retriever)

    practice = allowed_tools(profile_for_agent("practice"), None)
    assert "web_search" not in practice and "write_file" not in practice

    assert allowed_tools(profile_for_agent("progress"), None) == []


def test_app_wires_workspace(tmp_path) -> None:
    """组合根把工作区指到 data 目录下；不配置时回落到 data/workspace。"""

    from fastapi.testclient import TestClient

    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)):
        # 显式设定用户：别的测试文件可能泄漏 contextvar，这里不依赖全局状态
        tools.set_current_user("local")
        out = tools.write_file.invoke({"filename": "hello.md", "content": "hi"})
        assert "已写入" in out, out
        expected = tmp_path / "workspace" / "local" / "hello.md"
        assert expected.exists(), f"应落在本次测试的 tmp 工作区：{out}"


def test_tavily_takes_priority_and_formats(monkeypatch) -> None:
    """配置了 Tavily Key → 走 Tavily；没配 / 失败 → 回落 DuckDuckGo。"""

    from studygraph.config import Settings

    monkeypatch.setattr(
        tools, "_workspace_dir", lambda: __import__("pathlib").Path("/tmp/ignore")
    )
    monkeypatch.setattr(
        "studygraph.config.get_settings",
        lambda: Settings(tavily_api_key="tvly-test"),
    )
    calls = {"tavily": 0, "ddg": 0}

    def fake_tavily(query, n):
        calls["tavily"] += 1
        return [{"title": "T", "body": "B", "href": "https://t.example/a"}]

    def fake_ddg(query, n):
        calls["ddg"] += 1
        return [{"title": "D", "body": "B2", "href": "https://d.example/a"}]

    monkeypatch.setattr(tools, "_tavily_text", fake_tavily)
    monkeypatch.setattr(tools, "_ddg_text", fake_ddg)

    out = tools.web_search.invoke({"query": "六级作文"})
    assert calls["tavily"] == 1 and calls["ddg"] == 0
    assert "【T】" in out

    # Tavily 失败 → 回落 DDG
    def broken_tavily(query, n):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(tools, "_tavily_text", broken_tavily)
    out = tools.web_search.invoke({"query": "六级作文"})
    assert calls["ddg"] == 1 and "【D】" in out

    # 没配 Key → 直接 DDG
    monkeypatch.setattr(
        "studygraph.config.get_settings", lambda: Settings(tavily_api_key="")
    )
    out = tools.web_search.invoke({"query": "六级作文"})
    assert calls["ddg"] == 2
