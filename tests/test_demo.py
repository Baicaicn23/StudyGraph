from __future__ import annotations

from pathlib import Path

from studygraph.config import Settings
from studygraph.infrastructure.knowledge import KnowledgeStore
from studygraph.infrastructure.learning_repository import SqliteLearningRepository
from studygraph.interfaces.demo import DEMO_MISTAKES, DEMO_NOTES, seed


def test_seed_populates_libraries_notes_and_mistakes(tmp_path: Path) -> None:
    settings = Settings(database_path=str(tmp_path / "demo.db"))

    result = seed(settings, user_id="local")

    assert result["notes"] == sum(len(notes) for notes in DEMO_NOTES.values())
    knowledge = KnowledgeStore(settings.database_path)
    names = {item["name"] for item in knowledge.list_libraries()}
    assert set(DEMO_NOTES) <= names
    repository = SqliteLearningRepository(settings.database_path)
    assert len(repository.list_feedback("local")) == len(DEMO_MISTAKES)


def test_seeded_corpus_is_searchable(tmp_path: Path) -> None:
    settings = Settings(database_path=str(tmp_path / "demo.db"))
    seed(settings)
    knowledge = KnowledgeStore(settings.database_path)

    hits = knowledge.search("定积分和不定积分有什么区别", libraries=["高等数学-微积分"])

    assert hits
    assert any("定积分" in hit.title for hit in hits)
