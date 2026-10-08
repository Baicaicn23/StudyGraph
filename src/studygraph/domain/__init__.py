"""领域层：纯业务逻辑。

这一层是洋葱的中心——**不依赖任何外部框架**（FastAPI、LangGraph、SQLite、
模型 SDK 都不许 import），只用标准库。所有涉及"学习这件事本身"的规则都放这里，
因此可以被最快、最确定地单元测试。
"""

from .errors import DomainError, LearningError
from .models import Chunk, SearchHit
from .quiz import (
    WrittenQuestion,
    build_excerpt_instruction,
    build_mistake_instruction,
    parse_question,
    template_excerpt_question,
    template_mistake_question,
)
from .retrieval import chunk_text, rrf_fuse
from .scheduling import RATINGS, ReviewResult, clamp_mastery, review

__all__ = [
    "RATINGS",
    "Chunk",
    "DomainError",
    "LearningError",
    "ReviewResult",
    "SearchHit",
    "WrittenQuestion",
    "build_excerpt_instruction",
    "build_mistake_instruction",
    "chunk_text",
    "clamp_mastery",
    "parse_question",
    "review",
    "rrf_fuse",
    "template_excerpt_question",
    "template_mistake_question",
]
