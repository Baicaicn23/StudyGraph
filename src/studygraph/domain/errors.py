"""领域异常：表达"业务规则不允许"，与 HTTP/DB 无关。"""

from __future__ import annotations


class DomainError(ValueError):
    """领域层错误基类。"""


class LearningError(DomainError):
    """学习闭环相关的业务错误（如评分非法、没有可用错题）。"""
