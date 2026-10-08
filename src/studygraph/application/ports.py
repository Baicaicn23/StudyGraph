"""端口（Ports）：应用层对外部世界的**抽象**。

洋葱架构的关键是"依赖倒置"——应用层不 import 具体实现（SQLite、OpenAI），
只依赖这里定义的 Protocol；具体实现在 `infrastructure/` 里提供。这样换数据库、
换模型、换检索实现都不需要改业务代码，测试时也可以塞假实现。
"""

from __future__ import annotations

from typing import Any, Protocol

from ..domain.models import Chunk, SearchHit


class KnowledgePort(Protocol):
    """学科知识库：检索与写入。"""

    def search(
        self, query: str, *, libraries: list[str] | None = None, limit: int = 4
    ) -> list[SearchHit]: ...

    def list_libraries(self) -> list[dict[str, object]]: ...

    def add_document(self, library: str, title: str, content: str) -> int: ...

    def list_chunks(self, *, library: str | None = None) -> list[Chunk]: ...


class LearningRepositoryPort(Protocol):
    """学习闭环的持久化：错题 / 练习题 / 掌握度 / 记忆。"""

    def add_feedback(
        self, *, user_id: str, library: str, question: str, note: str
    ) -> int: ...

    def list_feedback(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]: ...

    def insert_question(
        self,
        *,
        user_id: str,
        library: str,
        prompt: str,
        source: str,
        source_chunk_id: int | None,
        source_feedback_id: int | None,
    ) -> int: ...

    def used_chunk_ids(self, user_id: str) -> set[int]: ...

    def unused_mistakes(
        self, user_id: str, library: str, *, limit: int
    ) -> list[dict[str, Any]]: ...

    def get_question_library(self, user_id: str, question_id: int) -> str | None: ...

    def update_question_review(
        self, question_id: int, *, due_at: float, rating: str
    ) -> None: ...

    def record_attempt(
        self, question_id: int, rating: str, *, created_at: float
    ) -> None: ...

    def get_mastery(self, user_id: str, library: str) -> int: ...

    def set_mastery(
        self, user_id: str, library: str, mastery: int, *, updated_at: float
    ) -> None: ...

    def list_progress(self, user_id: str) -> list[dict[str, Any]]: ...

    def due_questions(
        self, user_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]: ...

    def remember_fact(self, user_id: str, content: str, *, created_at: float) -> None: ...

    def list_memories(self, user_id: str, *, limit: int = 10) -> list[str]: ...

    def count_recent_mistakes(self, user_id: str, *, since: float) -> int: ...


class EmbeddingPort(Protocol):
    """向量化。"""

    @property
    def dim(self) -> int: ...

    @property
    def name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatModelPort(Protocol):
    """聊天模型（LangGraph 节点里调用）。"""

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any: ...
