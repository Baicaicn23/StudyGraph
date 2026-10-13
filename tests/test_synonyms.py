from __future__ import annotations

import json
from pathlib import Path

from zhiji.domain.synonyms import (
    DEFAULT_GROUPS,
    expand_terms,
    load_synonym_groups,
)


def test_expand_terms_finds_chinese_alias() -> None:
    """中文异名：本征值 → 特征值。"""

    assert "特征值" in expand_terms("本征值和本征向量是什么")


def test_expand_terms_is_case_insensitive_for_english() -> None:
    """中英对照：QUEUE → 队列（大小写不敏感）。"""

    expanded = expand_terms("QUEUE 这种结构的特点")
    assert "队列" in expanded


def test_expand_terms_skips_terms_already_in_query() -> None:
    """查询里已经写了的术语不必再扩一遍。"""

    expanded = expand_terms("特征值到底指什么")
    assert "特征值" not in expanded
    assert "本征值" in expanded


def test_expand_terms_no_match_returns_empty() -> None:
    assert expand_terms("今天天气不错") == []
    assert expand_terms("") == []


def test_expand_terms_respects_ascii_word_boundary() -> None:
    """英文按词边界匹配——"sort" 不该被 "consortium" 这类词触发。"""

    assert expand_terms("consortium") == []


def test_expand_terms_can_be_disabled() -> None:
    """传空组表 = 关闭扩写。"""

    assert expand_terms("本征值", ()) == []


def test_expand_terms_uses_custom_groups() -> None:
    groups = (("范式", "normal form"),)
    assert expand_terms("范式是什么", groups) == ["normal form"]


def test_default_groups_are_wellformed() -> None:
    """内置表每组至少两个术语、无空串、无组内重复。"""

    for group in DEFAULT_GROUPS:
        assert len(group) >= 2
        assert all(term.strip() for term in group)
        assert len(set(group)) == len(group)


def test_load_synonym_groups_appends_user_file(tmp_path: Path) -> None:
    file = tmp_path / "synonyms.json"
    file.write_text(
        json.dumps([["微积分", "高等数学"], ["没有同义词"]], ensure_ascii=False),
        encoding="utf-8",
    )

    groups = load_synonym_groups(file)

    # 单术语组（不足两个）被忽略
    assert ("微积分", "高等数学") in groups
    assert all(len(group) >= 2 for group in groups)
    # 内置组仍在
    assert ("特征值", "本征值") in groups


def test_load_synonym_groups_tolerates_bad_input(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    not_a_list = tmp_path / "obj.json"
    not_a_list.write_text('{"a": 1}', encoding="utf-8")

    for path in (missing, broken, not_a_list):
        groups = load_synonym_groups(path)
        assert ("特征值", "本征值") in groups  # 回落内置表，不抛异常
    assert load_synonym_groups("") == DEFAULT_GROUPS
