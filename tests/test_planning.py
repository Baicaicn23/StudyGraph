from __future__ import annotations

from zhiji.domain.model_routing import model_tier, reasoning_effort
from zhiji.domain.planning import fallback_plan, is_complex, parse_plan


def test_is_complex_heuristics() -> None:
    assert is_complex("讲解一下导数") is False
    assert is_complex("请一步步教我：先讲定义，然后讲几何意义") is True
    assert is_complex("x" * 50) is True


def test_fallback_plan_is_short_and_non_empty() -> None:
    plan = fallback_plan("任意请求")
    assert 2 <= len(plan) <= 5
    assert all(isinstance(step, str) and step for step in plan)


def test_parse_plan_accepts_json_array() -> None:
    assert parse_plan('["第一步", "第二步"]') == ["第一步", "第二步"]
    assert parse_plan('```json\n["甲", "乙"]\n```') == ["甲", "乙"]
    assert parse_plan("不是计划") is None
    assert parse_plan("[]") is None


def test_model_tier_by_intent_and_length() -> None:
    assert model_tier("calculation", "7 * 9") == "small"
    assert model_tier("smalltalk", "你好") == "small"
    assert model_tier("concept_explain", "讲解导数") == "standard"
    assert model_tier("concept_explain", "x" * 80) == "large"


def test_reasoning_effort_by_intent() -> None:
    """重思考意图拉满、轻意图压 low、中间档交模型自动判断（None）。"""

    assert reasoning_effort("concept_explain", "讲解导数") == "max"
    assert reasoning_effort("practice", "出几道题") == "max"
    assert reasoning_effort("calculation", "7 * 9") == "low"
    assert reasoning_effort("smalltalk", "你好") == "low"
    assert reasoning_effort("retrieval", "帮我查一下资料") is None
    # 轻意图优先：闲聊即使很长也压 low（长文本只在非轻意图时升级 max）
    assert reasoning_effort("smalltalk", "x" * 80) == "low"
    assert reasoning_effort("retrieval", "x" * 80) == "max"
