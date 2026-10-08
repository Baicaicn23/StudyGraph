from __future__ import annotations

from studygraph.domain.model_routing import model_tier
from studygraph.domain.planning import fallback_plan, is_complex, parse_plan


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
