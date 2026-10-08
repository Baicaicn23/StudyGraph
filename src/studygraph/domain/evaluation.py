"""评测指标（纯函数）。

- `hit_at_k`：正确项有没有出现在前 k 条召回里。
- `reciprocal_rank`：正确项排第几（第 1 名 1.0、第 2 名 0.5、第 3 名 0.33 …）。
- `mean`：把这些数平均成 MRR / Hit@K。

只依赖标准库，可被一行断言测清楚。
"""

from __future__ import annotations


def hit_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    return 1.0 if any(item in gold for item in ranked[:k]) else 0.0


def reciprocal_rank(ranked: list[str], gold: set[str]) -> float:
    for rank, item in enumerate(ranked, start=1):
        if item in gold:
            return 1.0 / rank
    return 0.0


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
