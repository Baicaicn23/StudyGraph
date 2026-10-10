"""学习闭环用例：错题 / 出题 / 复习 / 长期记忆 / 今日复习。

只依赖端口（`ports.py`）和领域规则（`domain/`），不 import 任何基础设施。
"""

from __future__ import annotations

import time
from typing import Any

from ..domain.errors import LearningError
from ..domain.memory import extract_facts
from ..domain.quiz import (
    build_excerpt_instruction,
    build_mistake_instruction,
    normalize_difficulty,
    template_excerpt_question,
    template_mistake_question,
)
from ..domain.scheduling import review
from .ports import ChatModelPort, KnowledgePort, LearningRepositoryPort
from .question_writer import write_question

SOURCES = ("knowledge_base", "mistakes")
_WEEK_SECONDS = 7 * 24 * 60 * 60
_WEAK_MASTERY = 60
# auto 难度分档：按学科掌握度自动选档，贴合"最近发展区"。
_DIFFICULTY_BY_MASTERY = ((40, "basic"), (80, "apply"))  # >=80 → transfer


class LearningService:
    def __init__(
        self, knowledge: KnowledgePort, repository: LearningRepositoryPort
    ) -> None:
        self.knowledge = knowledge
        self.repository = repository

    def _resolve_difficulty(self, user_id: str, library: str, difficulty: str) -> str:
        """把请求难度解析成三档之一；`auto` 按当前学科掌握度自动分档。"""

        if difficulty == "auto":
            mastery = self.repository.get_mastery(user_id, library)
            for threshold, tier in _DIFFICULTY_BY_MASTERY:
                if mastery < threshold:
                    return tier
            return "transfer"
        resolved = normalize_difficulty(difficulty)
        if resolved is None:
            raise LearningError(
                "难度只能是 basic（基础）/ apply（进阶）/ transfer（迁移）/ auto"
            )
        return resolved

    # -- 错题 -----------------------------------------------------------------

    def add_feedback(
        self, *, user_id: str, library: str, question: str, note: str
    ) -> int:
        return self.repository.add_feedback(
            user_id=user_id, library=library, question=question, note=note
        )

    def list_feedback(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.list_feedback(user_id, limit=limit)

    # -- 出题 -----------------------------------------------------------------

    async def generate(
        self,
        *,
        user_id: str,
        source: str = "knowledge_base",
        library: str = "",
        count: int = 3,
        model: ChatModelPort | None = None,
        difficulty: str = "auto",
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 10:
            raise LearningError("每次可生成 1 到 10 道练习题")
        if source not in SOURCES:
            raise LearningError(f"不支持的出题来源：{source}")
        if difficulty != "auto" and normalize_difficulty(difficulty) is None:
            raise LearningError(
                "难度只能是 basic（基础）/ apply（进阶）/ transfer（迁移）/ auto"
            )
        if source == "mistakes":
            return await self._from_mistakes(
                user_id=user_id,
                library=library,
                count=count,
                model=model,
                difficulty=difficulty,
            )
        return await self._from_library(
            user_id=user_id,
            library=library,
            count=count,
            model=model,
            difficulty=difficulty,
        )

    async def _from_library(
        self,
        *,
        user_id: str,
        library: str,
        count: int,
        model: ChatModelPort | None,
        difficulty: str,
    ) -> list[dict[str, Any]]:
        if not library.strip():
            raise LearningError("请先选择知识库")
        resolved = self._resolve_difficulty(user_id, library, difficulty)
        used = self.repository.used_chunk_ids(user_id)
        candidates = [
            chunk
            for chunk in self.knowledge.list_chunks(library=library)
            if chunk.id not in used
        ][:count]
        if not candidates:
            raise LearningError("这个知识库里暂时没有可用于出题的新片段")
        created: list[dict[str, Any]] = []
        for chunk in candidates:
            written = await write_question(
                model,
                build_excerpt_instruction(chunk.content, resolved),
                fallback=template_excerpt_question(chunk.content, resolved),
            )
            created.append(
                self._store_question(
                    user_id=user_id,
                    library=library,
                    written_prompt=written.prompt,
                    generator=written.generator,
                    source="knowledge_base",
                    source_chunk_id=chunk.id,
                    source_feedback_id=None,
                    difficulty=resolved,
                )
            )
        return created

    async def _from_mistakes(
        self,
        *,
        user_id: str,
        library: str,
        count: int,
        model: ChatModelPort | None,
        difficulty: str,
    ) -> list[dict[str, Any]]:
        rows = self.repository.unused_mistakes(user_id, library, limit=count)
        if not rows:
            raise LearningError("还没有可用于出题的新错题：先记录一条误区")
        created: list[dict[str, Any]] = []
        for row in rows:
            question = str(row["question"])
            note = str(row["note"])
            # 每条误区按它自己学科的掌握度分档（auto 时）。
            resolved = self._resolve_difficulty(user_id, str(row["library"]), difficulty)
            written = await write_question(
                model,
                build_mistake_instruction(
                    subject=str(row["library"]),
                    question=question,
                    note=note,
                    difficulty=resolved,
                ),
                fallback=template_mistake_question(
                    question=question, note=note, difficulty=resolved
                ),
            )
            created.append(
                self._store_question(
                    user_id=user_id,
                    library=str(row["library"]),
                    written_prompt=written.prompt,
                    generator=written.generator,
                    source="mistake",
                    source_chunk_id=None,
                    source_feedback_id=int(row["id"]),
                    difficulty=resolved,
                )
            )
        return created

    def _store_question(
        self,
        *,
        user_id: str,
        library: str,
        written_prompt: str,
        generator: str,
        source: str,
        source_chunk_id: int | None,
        source_feedback_id: int | None,
        difficulty: str = "basic",
    ) -> dict[str, Any]:
        question_id = self.repository.insert_question(
            user_id=user_id,
            library=library,
            prompt=written_prompt,
            source=source,
            source_chunk_id=source_chunk_id,
            source_feedback_id=source_feedback_id,
            difficulty=difficulty,
        )
        return {
            "id": question_id,
            "library": library,
            "prompt": written_prompt,
            "source": source,
            "generator": generator,
            "difficulty": difficulty,
            "due_at": time.time(),
        }

    # -- 复习与间隔重复 -------------------------------------------------------

    def due_questions(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.due_questions(user_id, limit=limit)

    def answer(
        self, *, user_id: str, question_id: int, rating: str
    ) -> dict[str, Any]:
        library = self.repository.get_question_library(user_id, question_id)
        if library is None:
            raise LearningError("找不到这道题")
        outcome = review(rating, self.repository.get_mastery(user_id, library))
        now = time.time()
        due_at = now + outcome.due_in_seconds if outcome.due_in_seconds > 0 else now
        self.repository.update_question_review(
            question_id, due_at=due_at, rating=rating
        )
        self.repository.record_attempt(question_id, rating, created_at=now)
        self.repository.set_mastery(
            user_id, library, outcome.mastery, updated_at=now
        )
        return {
            "question_id": question_id,
            "library": library,
            "rating": rating,
            "mastery": outcome.mastery,
            "due_at": due_at,
            "due_in_days": outcome.due_in_days,
        }

    def progress(self, user_id: str) -> list[dict[str, Any]]:
        return self.repository.list_progress(user_id)

    def activity_series(self, user_id: str, *, days: int) -> list[dict[str, Any]]:
        """近 N 天学习活跃度（练习量 + 新增误区，按天聚合），供热力图使用。"""

        return self.repository.activity_series(user_id, days=days)

    # -- 长期记忆 -------------------------------------------------------------

    def delete_feedback(self, user_id: str, feedback_id: int) -> bool:
        return self.repository.delete_feedback(user_id, feedback_id)

    def delete_question(self, user_id: str, question_id: int) -> bool:
        return self.repository.delete_question(user_id, question_id)

    def delete_memory(self, user_id: str, memory_id: int) -> bool:
        return self.repository.delete_memory(user_id, memory_id)

    def remember(
        self, user_id: str, text: str, *, project_id: str = ""
    ) -> list[str]:
        facts = extract_facts(text)
        now = time.time()
        for fact in facts:
            self.repository.remember_fact(
                user_id, fact, created_at=now, project_id=project_id
            )
        return facts

    def memories(
        self, user_id: str, *, project_id: str = "", limit: int = 10
    ) -> list[dict[str, Any]]:
        return self.repository.list_memories(
            user_id, project_id=project_id, limit=limit
        )

    # -- 今日复习 -------------------------------------------------------------

    def plan(self, user_id: str) -> dict[str, Any]:
        due = self.repository.due_questions(user_id, limit=20)
        weak = [
            item
            for item in self.repository.list_progress(user_id)
            if int(item["mastery"]) < _WEAK_MASTERY
        ]
        recent = self.repository.count_recent_mistakes(
            user_id, since=time.time() - _WEEK_SECONDS
        )

        suggestions: list[str] = []
        if due:
            suggestions.append(f"先做 {len(due)} 道到期练习题")
        for item in weak:
            suggestions.append(f"复习「{item['library']}」（掌握度 {item['mastery']}%）")
        if recent:
            suggestions.append(f"回看最近记录的 {recent} 条误区")
        if not suggestions:
            suggestions.append("暂时没有到期任务，可以上传新资料或记录一条误区")

        return {
            "due_questions": due,
            "weak_libraries": weak,
            "recent_mistakes": recent,
            "suggestions": suggestions,
        }

    # -- 考前冲刺计划 ---------------------------------------------------------

    _SPRINT_QUOTA = 3  # 非清题日每天巩固的练习题量

    def sprint(self, user_id: str, *, days: int = 7) -> dict[str, Any]:
        """考前冲刺：按「最薄弱优先」把到期题与练习任务排进未来 N 天。

        纯确定性计算（零模型调用），输入只有三样：各库掌握度、到期练习、
        近一周误区数——数据不撒谎，答辩可复现。
        """

        if days < 1 or days > 30:
            raise LearningError("冲刺周期只能是 1 到 30 天")

        progress = self.repository.list_progress(user_id)
        due = self.repository.due_questions(user_id, limit=100)
        recent_mistakes = self.repository.count_recent_mistakes(
            user_id, since=time.time() - _WEEK_SECONDS
        )

        mastery_by_library = {str(row["library"]): int(row["mastery"]) for row in progress}
        due_by_library: dict[str, int] = {}
        for item in due:
            library = str(item["library"])
            due_by_library[library] = due_by_library.get(library, 0) + 1
            # 有到期题说明练过但没有掌握度记录（旧库/异常路径），按 0 分对待
            mastery_by_library.setdefault(library, 0)

        if not mastery_by_library:
            return {
                "days": days,
                "schedule": [],
                "total_due": 0,
                "weak_libraries": [],
                "recent_mistakes": recent_mistakes,
                "hint": "还没有学习数据：先在知识库上传资料、做几道练习，再回来生成冲刺计划。",
            }

        # 最薄弱优先；掌握度相同时到期题多的库先安排
        order = sorted(
            mastery_by_library,
            key=lambda lib: (mastery_by_library[lib], -due_by_library.get(lib, 0)),
        )

        pending_due = dict(due_by_library)
        schedule: list[dict[str, Any]] = []
        now = time.time()
        for index in range(days):
            library = order[index % len(order)]
            mastery = mastery_by_library[library]
            tasks: list[str] = []
            if index == 0 and recent_mistakes:
                tasks.append(f"回看最近记录的 {recent_mistakes} 条误区")
            remaining = pending_due.get(library, 0)
            if remaining > 0:
                tasks.append(f"清完「{library}」的 {remaining} 道到期练习")
                pending_due[library] = 0
            else:
                tasks.append(
                    f"从「{library}」出 {self._SPRINT_QUOTA} 道练习题（难度 auto，按掌握度分档）"
                )
            if mastery < _WEAK_MASTERY:
                tasks.append(f"重读「{library}」笔记里的易错点，目标把掌握度拉离 {mastery}%")
            if index == days - 1 and days > 1:
                tasks.append("收官自测：把到期题清零，做错的题回炉到错题本")
            schedule.append(
                {
                    "day": index + 1,
                    "date": time.strftime("%Y-%m-%d", time.localtime(now + index * 86400)),
                    "focus": library,
                    "mastery": mastery,
                    "tasks": tasks,
                }
            )

        return {
            "days": days,
            "schedule": schedule,
            "total_due": len(due),
            "weak_libraries": [
                row for row in progress if int(row["mastery"]) < _WEAK_MASTERY
            ],
            "recent_mistakes": recent_mistakes,
            "hint": "",
        }
