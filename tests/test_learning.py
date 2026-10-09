from __future__ import annotations

from pathlib import Path

import pytest

from studygraph.application.learning_service import LearningService
from studygraph.domain.errors import LearningError
from studygraph.infrastructure.knowledge import KnowledgeStore
from studygraph.infrastructure.learning_repository import SqliteLearningRepository


def _services(tmp_path: Path) -> tuple[KnowledgeStore, LearningService]:
    db = tmp_path / "learn.db"
    knowledge = KnowledgeStore(db)
    repository = SqliteLearningRepository(db)
    return knowledge, LearningService(knowledge, repository)


async def test_generate_from_library_uses_template_and_exhausts(tmp_path: Path) -> None:
    knowledge, learning = _services(tmp_path)
    knowledge.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")
    knowledge.add_note("高等数学", "积分", "定积分是累积量，不定积分是函数族。")

    questions = await learning.generate(
        user_id="u1", source="knowledge_base", library="高等数学", count=3, model=None
    )

    assert len(questions) == 2
    assert all(q["source"] == "knowledge_base" for q in questions)
    assert all(q["generator"] == "template" for q in questions)

    with pytest.raises(LearningError):
        await learning.generate(
            user_id="u1", source="knowledge_base", library="高等数学", count=3
        )


async def test_generate_requires_library(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    with pytest.raises(LearningError):
        await learning.generate(user_id="u1", source="knowledge_base", library="")


async def test_generate_from_mistakes_one_question_each(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    learning.add_feedback(
        user_id="u1", library="线性代数", question="什么是特征值？", note="我把特征向量搞混了"
    )
    learning.add_feedback(
        user_id="u1", library="微积分", question="定积分和不定积分？", note="结果类型搞混"
    )
    learning.add_feedback(user_id="u1", library="", question="随手问", note="没有学科")

    questions = await learning.generate(
        user_id="u1", source="mistakes", count=5, model=None
    )

    assert len(questions) == 2  # 无学科的误区不出题
    assert {q["library"] for q in questions} == {"线性代数", "微积分"}
    assert all(q["source"] == "mistake" for q in questions)

    # 一条误区只出一道题：再生成就没有新的了。
    with pytest.raises(LearningError):
        await learning.generate(user_id="u1", source="mistakes", count=5)


async def test_generate_from_mistakes_respects_library_filter(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    learning.add_feedback(
        user_id="u1", library="线性代数", question="q1", note="n1"
    )
    learning.add_feedback(user_id="u1", library="微积分", question="q2", note="n2")

    questions = await learning.generate(
        user_id="u1", source="mistakes", library="微积分", count=5
    )

    assert len(questions) == 1
    assert questions[0]["library"] == "微积分"


async def test_answer_updates_mastery_and_schedule(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    learning.add_feedback(user_id="u1", library="线性代数", question="q", note="n")
    [question] = await learning.generate(user_id="u1", source="mistakes", count=1)

    result = learning.answer(user_id="u1", question_id=question["id"], rating="good")
    assert result["mastery"] == 5
    assert result["due_in_days"] == 3.0

    result = learning.answer(user_id="u1", question_id=question["id"], rating="again")
    assert result["mastery"] == 0  # 5 - 10，被夹到 0
    assert result["due_in_days"] == 0.0  # again 立即再来


def test_answer_rejects_unknown_rating(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    with pytest.raises(LearningError):
        learning.answer(user_id="u1", question_id=1, rating="perfect")


async def test_plan_summarizes_weak_and_due(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    learning.add_feedback(user_id="u1", library="线性代数", question="q", note="n")
    questions = await learning.generate(user_id="u1", source="mistakes", count=1)
    learning.answer(user_id="u1", question_id=questions[0]["id"], rating="again")

    plan = learning.plan("u1")

    assert plan["due_questions"]
    assert any("线性代数" in item for item in plan["suggestions"])


def test_remember_and_list_memories(tmp_path: Path) -> None:
    _knowledge, learning = _services(tmp_path)
    assert learning.remember("u1", "记住：我在准备月底的微积分测验") == ["我在准备月底的微积分测验"]
    assert [m["content"] for m in learning.memories("u1")] == [
        "我在准备月底的微积分测验"
    ]
    # 去重
    learning.remember("u1", "记住：我在准备月底的微积分测验")
    assert len(learning.memories("u1")) == 1
