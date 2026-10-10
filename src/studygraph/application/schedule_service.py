"""日程用例：收件箱 → 时间轴的排期。

设计口径（与产品约定一致）：
- 时间轴固定显示 06:00–24:00（`_DAY_START` / `_DAY_END`），排期不落在这段之外的冷门时段；
- 「一键安排」是确定性规则而非模型：从当天已有任务的空隙里找**最早放得下的空档**，
  今天则从当前时刻之后开始找——同一天同一堆任务，排出来的结果永远一样（可测可复现）。
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from ..domain.errors import LearningError
from .ports import ScheduleRepositoryPort

# 时间轴可视范围：06:00 – 24:00
_DAY_START = 6 * 60
_DAY_END = 24 * 60
_MIN_DURATION = 5
_MAX_DURATION = 600
_DATE_FORMAT = "%Y-%m-%d"


def _parse_date(value: str) -> str:
    try:
        return datetime.datetime.strptime(value, _DATE_FORMAT).strftime(_DATE_FORMAT)
    except ValueError as exc:
        raise LearningError("日期格式必须是 YYYY-MM-DD") from exc


def _week_range(date: str) -> tuple[str, str]:
    """以周日开头的周区间（与前端周条一致）。"""

    day = datetime.datetime.strptime(date, _DATE_FORMAT).date()
    start = day - datetime.timedelta(days=(day.weekday() + 1) % 7)
    end = start + datetime.timedelta(days=6)
    return start.strftime(_DATE_FORMAT), end.strftime(_DATE_FORMAT)


class ScheduleService:
    def __init__(self, repository: ScheduleRepositoryPort) -> None:
        self.repository = repository

    # -- 校验 -----------------------------------------------------------------

    @staticmethod
    def _validate(
        *,
        title: str | None = None,
        start_minutes: int | None = None,
        duration_minutes: int | None = None,
        date: str | None = None,
    ) -> None:
        if title is not None and not title.strip():
            raise LearningError("任务标题不能为空")
        if title is not None and len(title.strip()) > 120:
            raise LearningError("任务标题最多 120 字")
        if start_minutes is not None and not 0 <= start_minutes < 24 * 60:
            raise LearningError("开始时间超出当天范围")
        if duration_minutes is not None and not (
            _MIN_DURATION <= duration_minutes <= _MAX_DURATION
        ):
            raise LearningError(f"时长要在 {_MIN_DURATION}–{_MAX_DURATION} 分钟之间")
        if date is not None:
            _parse_date(date)

    # -- 读 -------------------------------------------------------------------

    def day_view(self, user_id: str, date: str) -> dict[str, Any]:
        """某天的时间轴数据 + 收件箱计数（页面一次请求拿全）。"""

        clean = _parse_date(date)
        return {
            "date": clean,
            "tasks": self.repository.list_day(user_id, clean),
            "inbox_count": len(self.repository.list_inbox(user_id)),
        }

    def inbox(self, user_id: str) -> list[dict[str, Any]]:
        return self.repository.list_inbox(user_id)

    def week(self, user_id: str, date: str) -> dict[str, Any]:
        """周条密度：以 date 所在周（周日开头）的每天 排期数/完成数。"""

        clean = _parse_date(date)
        start, end = _week_range(clean)
        counts = {
            item["date"]: item
            for item in self.repository.count_by_date(user_id, start=start, end=end)
        }
        days: list[dict[str, Any]] = []
        cursor = datetime.datetime.strptime(start, _DATE_FORMAT).date()
        for _ in range(7):
            key = cursor.strftime(_DATE_FORMAT)
            item = counts.get(key, {"total": 0, "done": 0})
            days.append({"date": key, "total": item["total"], "done": item["done"]})
            cursor += datetime.timedelta(days=1)
        return {"start": start, "end": end, "days": days}

    # -- 写 -------------------------------------------------------------------

    def create(
        self,
        *,
        user_id: str,
        title: str,
        note: str = "",
        date: str | None = None,
        start_minutes: int | None = None,
        duration_minutes: int = 30,
    ) -> dict[str, Any]:
        self._validate(
            title=title,
            start_minutes=start_minutes,
            duration_minutes=duration_minutes,
            date=date,
        )
        clean_date = _parse_date(date) if date else None
        if clean_date is not None and start_minutes is None:
            # 直接放进某天但没给时间：自动安排进最早空档
            start_minutes = self._first_free_slot(
                user_id, clean_date, duration_minutes, respect_now=True
            )
        task_id = self.repository.create_task(
            user_id=user_id,
            title=title.strip(),
            note=note.strip(),
            date=clean_date,
            start_minutes=start_minutes if clean_date else None,
            duration_minutes=duration_minutes,
        )
        task = self.repository.get_task(user_id, task_id)
        assert task is not None  # 刚写入，必然存在
        return task

    def update(
        self,
        *,
        user_id: str,
        task_id: int,
        title: str | None = None,
        note: str | None = None,
        date: str | None = None,
        start_minutes: int | None = None,
        duration_minutes: int | None = None,
        done: bool | None = None,
    ) -> dict[str, Any]:
        if self.repository.get_task(user_id, task_id) is None:
            raise LearningError("任务不存在")
        self._validate(
            title=title,
            start_minutes=start_minutes,
            duration_minutes=duration_minutes,
            date=date,
        )
        updated = self.repository.update_task(
            user_id,
            task_id,
            title=title.strip() if title is not None else None,
            note=note.strip() if note is not None else None,
            date=_parse_date(date) if date else None,
            start_minutes=start_minutes,
            duration_minutes=duration_minutes,
            done=done,
        )
        if not updated:
            raise LearningError("没有需要更新的字段")
        task = self.repository.get_task(user_id, task_id)
        assert task is not None
        return task

    def arrange(
        self,
        *,
        user_id: str,
        task_id: int,
        date: str | None = None,
    ) -> dict[str, Any]:
        """一键安排到某天（缺省今天）的第一个空档。"""

        task = self.repository.get_task(user_id, task_id)
        if task is None:
            raise LearningError("任务不存在")
        target = _parse_date(date) if date else time.strftime(_DATE_FORMAT)
        duration = int(task["duration_minutes"])
        start = self._first_free_slot(user_id, target, duration, respect_now=True)
        self.repository.update_task(
            user_id,
            task_id,
            date=target,
            start_minutes=start,
            duration_minutes=duration,
        )
        arranged = self.repository.get_task(user_id, task_id)
        assert arranged is not None
        return arranged

    def unarrange(self, *, user_id: str, task_id: int) -> dict[str, Any]:
        """退回收件箱（保留时长，清掉日期与开始时间）。"""

        if self.repository.get_task(user_id, task_id) is None:
            raise LearningError("任务不存在")
        self.repository.update_task(user_id, task_id, clear_date=True)
        task = self.repository.get_task(user_id, task_id)
        assert task is not None
        return task

    def delete(self, *, user_id: str, task_id: int) -> bool:
        return self.repository.delete_task(user_id, task_id)

    # -- 排期算法 -------------------------------------------------------------

    def _first_free_slot(
        self, user_id: str, date: str, duration: int, *, respect_now: bool
    ) -> int:
        """找第一个放得下的空档；今天从当前时刻（向上取整到 5 分钟）之后找。"""

        earliest = _DAY_START
        if respect_now and date == time.strftime(_DATE_FORMAT):
            now = datetime.datetime.now()
            minutes = now.hour * 60 + now.minute
            earliest = max(earliest, min(_DAY_END, (minutes // 5 + 1) * 5))

        busy = [
            (int(task["start_minutes"]), int(task["duration_minutes"]))
            for task in self.repository.list_day(user_id, date)
            if task["start_minutes"] is not None
        ]
        busy.sort()

        cursor = earliest
        for start, length in busy:
            if start - cursor >= duration:
                return cursor
            cursor = max(cursor, start + length)
        # 全部排完仍放得下就接在最后一个任务后面；否则贴到时间轴末尾（允许视觉重叠）
        if cursor + duration <= _DAY_END:
            return cursor
        return max(_DAY_START, _DAY_END - duration)
