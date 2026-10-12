from __future__ import annotations

import time
from pathlib import Path

from zhiji.infrastructure.usage_repository import SqliteUsageRepository


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


def test_cached_tokens_recorded_and_summarized(tmp_path) -> None:
    """上下文缓存命中数：record 写入、summary 汇总——成本证明的数据源。"""

    repository = SqliteUsageRepository(tmp_path / "usage.db")
    repository.record(
        user_id="u1",
        model="deepseek-flash",
        input_tokens=1000,
        output_tokens=200,
        total_tokens=1200,
        cached_tokens=800,
        created_at=time.time(),
    )
    repository.record(
        user_id="u1",
        model="deepseek-flash",
        input_tokens=500,
        output_tokens=100,
        total_tokens=600,
        created_at=time.time() + 1,
    )
    summary = repository.summary(user_id="u1", since=0)
    assert len(summary) == 1
    assert summary[0]["input_tokens"] == 1500
    assert summary[0]["cached_tokens"] == 800
