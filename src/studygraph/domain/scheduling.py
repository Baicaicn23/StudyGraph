"""间隔重复与掌握度的领域规则。

纯计算、无副作用：给定"自评等级"和"当前掌握度"，算出"新掌握度"和"下次复习间隔"。
把它从数据库和 HTTP 里剥出来，就是为了让这条核心规则能被一行断言测清楚。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import LearningError

# 自评 -> (掌握度增减, 下次复习间隔秒数)。Again 立刻再来，Easy 拉长到一周。
_RATING: dict[str, tuple[int, int]] = {
    "again": (-10, 0),
    "hard": (-3, 24 * 60 * 60),
    "good": (5, 3 * 24 * 60 * 60),
    "easy": (10, 7 * 24 * 60 * 60),
}

RATINGS = tuple(_RATING)

_DAY_SECONDS = 24 * 60 * 60


def clamp_mastery(value: int) -> int:
    return max(0, min(100, value))


@dataclass(frozen=True)
class ReviewResult:
    mastery: int
    due_in_seconds: int

    @property
    def due_in_days(self) -> float:
        return round(self.due_in_seconds / _DAY_SECONDS, 2)


def review(rating: str, current_mastery: int) -> ReviewResult:
    """按自评更新掌握度并给出下次复习间隔。评分非法则抛 LearningError。"""

    if rating not in _RATING:
        raise LearningError("评分必须是 again / hard / good / easy 之一")
    delta, interval = _RATING[rating]
    return ReviewResult(
        mastery=clamp_mastery(current_mastery + delta),
        due_in_seconds=interval,
    )
