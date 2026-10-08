from __future__ import annotations

import time
from pathlib import Path

from studygraph.infrastructure.usage_repository import SqliteUsageRepository


def test_record_and_query_usage(tmp_path: Path) -> None:
    repository = SqliteUsageRepository(tmp_path / "usage.db")
    repo = repository
    repo.record(
        user_id="u1",
        model="study-mock",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        created_at=time.time(),
    )
    repo.record(
        user_id="u1",
        model="study-mock",
        input_tokens=5,
        output_tokens=5,
        total_tokens=10,
        created_at=time.time(),
    )
    repo.record(
        user_id="u2",
        model="other",
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        created_at=time.time(),
    )

    assert repo.total_since(user_id="u1", since=0) == 40
    assert repo.total_since(user_id="u2", since=0) == 2
    summary = repo.summary(user_id="u1", since=0)
    assert summary[0]["model"] == "study-mock"
    assert summary[0]["total_tokens"] == 40
    assert summary[0]["calls"] == 2


def test_total_since_respects_time_window(tmp_path: Path) -> None:
    repository = SqliteUsageRepository(tmp_path / "usage.db")
    repository.record(
        user_id="u1",
        model="m",
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        created_at=time.time() - 100000,
    )
    assert repository.total_since(user_id="u1", since=time.time() - 10) == 0
