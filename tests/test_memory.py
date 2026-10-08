from __future__ import annotations

from studygraph.memory import extract_facts


def test_extract_explicit_remember_command() -> None:
    assert extract_facts("记住：我在准备月底的微积分测验") == ["我在准备月底的微积分测验"]


def test_extract_goal_and_identity() -> None:
    assert extract_facts("我的目标是四级作文拿到 12 分") == ["四级作文拿到 12 分"]
    assert extract_facts("我是一名大二学生") == ["大二学生"]


def test_extract_returns_empty_for_plain_question() -> None:
    assert extract_facts("帮我算一下 3 * 4") == []
    assert extract_facts("") == []
