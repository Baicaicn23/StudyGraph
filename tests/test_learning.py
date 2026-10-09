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


async def test_generate_difficulty_explicit_and_invalid(tmp_path: Path) -> None:
    knowledge, learning = _services(tmp_path)
    knowledge.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")

    # 显式难度落到生成的题目上（含模板兜底题面里的难度标记）。
    questions = await learning.generate(
        user_id="u1",
        source="knowledge_base",
        library="高等数学",
        count=1,
        model=None,
        difficulty="transfer",
    )
    assert questions[0]["difficulty"] == "transfer"
    assert "迁移" in questions[0]["prompt"]

    # 非法难度直接拒绝。
    with pytest.raises(LearningError):
        await learning.generate(
            user_id="u1",
            source="knowledge_base",
            library="高等数学",
            difficulty="impossible",
        )


async def test_generate_difficulty_auto_follows_mastery(tmp_path: Path) -> None:
    knowledge, learning = _services(tmp_path)
    knowledge.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")
    knowledge.add_note("线性代数", "特征值", "特征值描述线性变换的缩放倍数。")
    knowledge.add_note("大学物理", "加速度", "加速度是速度对时间的导数。")

    # 掌握度 20 → 基础；60 → 进阶；90 → 迁移（auto 分档）。
    learning.repository.set_mastery("u1", "高等数学", 20, updated_at=0)
    learning.repository.set_mastery("u1", "线性代数", 60, updated_at=0)
    learning.repository.set_mastery("u1", "大学物理", 90, updated_at=0)

    basic = await learning.generate(
        user_id="u1", source="knowledge_base", library="高等数学", count=1,
        model=None, difficulty="auto",
    )
    apply_ = await learning.generate(
        user_id="u1", source="knowledge_base", library="线性代数", count=1,
        model=None, difficulty="auto",
    )
    transfer = await learning.generate(
        user_id="u1", source="knowledge_base", library="大学物理", count=1,
        model=None, difficulty="auto",
    )

    assert basic[0]["difficulty"] == "basic"
    assert apply_[0]["difficulty"] == "apply"
    assert transfer[0]["difficulty"] == "transfer"


async def test_difficulty_survives_storage_roundtrip(tmp_path: Path) -> None:
    knowledge, learning = _services(tmp_path)
    knowledge.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")

    created = await learning.generate(
        user_id="u1",
        source="knowledge_base",
        library="高等数学",
        count=1,
        model=None,
        difficulty="apply",
    )

    due = learning.due_questions("u1")
    assert len(due) == 1
    assert due[0]["difficulty"] == "apply"
    assert due[0]["id"] == created[0]["id"]


async def test_repository_migrates_legacy_db_without_difficulty(
    tmp_path: Path,
) -> None:
    import sqlite3

    from studygraph.infrastructure.learning_repository import SqliteLearningRepository

    db = tmp_path / "legacy.db"
    # 手工造一个"旧版"practice_questions（没有 difficulty 列）。
    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE practice_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                library TEXT NOT NULL,
                prompt TEXT NOT NULL,
                source TEXT NOT NULL,
                source_chunk_id INTEGER,
                source_feedback_id INTEGER,
                created_at REAL NOT NULL,
                due_at REAL NOT NULL,
                answered_count INTEGER NOT NULL DEFAULT 0,
                last_rating TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO practice_questions (user_id, library, prompt, source, "
            "created_at, due_at) VALUES ('u0', '旧库', '旧题', 'knowledge_base', 0, 0)"
        )

    repository = SqliteLearningRepository(db)  # 构造时应自动补列

    columns = {
        row["name"]
        for row in repository._connect().execute(
            "PRAGMA table_info(practice_questions)"
        ).fetchall()
    }
    assert "difficulty" in columns
    # 旧数据按默认 basic 读取；insert 带难度也正常。
    assert repository.due_questions("u0")[0]["difficulty"] == "basic"
    repository.insert_question(
        user_id="u0",
        library="旧库",
        prompt="新题",
        source="knowledge_base",
        source_chunk_id=None,
        source_feedback_id=None,
        difficulty="transfer",
    )
    assert repository.due_questions("u0")[-1]["difficulty"] == "transfer"


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
