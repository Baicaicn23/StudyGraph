"""Embedding（向量化）与相似度。

两个实现：
- `MockHashEmbedding`：把文本按字符 n-gram 哈希进固定维度并 L2 归一化。
  它是**确定性**的、零成本的，且共享子串的文本会有更高余弦相似度——足以让
  "向量检索 + RRF 融合"这条链路在没有真实模型时也能被测试和演示。
- `OpenAIEmbedding`：任何 OpenAI 兼容的 `/embeddings` 接口（可选）。

相似度用**余弦**：向量都已归一化，余弦即点积。
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

_CJK_WS = re.compile(r"\s+")


class BaseEmbedding(ABC):
    name: str = "embedding"

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度。未知时返回 0（由首次调用确定）。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _ngrams(text: str) -> list[str]:
    cleaned = _CJK_WS.sub("", text or "")
    if not cleaned:
        return []
    grams: list[str] = []
    for size in (2, 3):
        grams.extend(cleaned[i : i + size] for i in range(len(cleaned) - size + 1))
    return grams or [cleaned]


class MockHashEmbedding(BaseEmbedding):
    def __init__(self, dim: int = 256) -> None:
        self._dim = dim
        self.name = f"mock-hash-{dim}"

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for gram in _ngrams(text):
            digest = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
            index = digest % self._dim
            sign = 1.0 if (digest >> 1) & 1 else -1.0
            vector[index] += sign
        return _l2_normalize(vector)


class OpenAIEmbedding(BaseEmbedding):
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.name = model
        self._base = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._key = api_key
        self._dim = 0

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        response = httpx.post(
            f"{self._base}/embeddings",
            headers={"Authorization": f"Bearer {self._key}"},
            json={"model": self.name, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in data]
        if vectors:
            self._dim = len(vectors[0])
        return vectors


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b, strict=True)))


def get_embedder(settings) -> BaseEmbedding:
    provider = getattr(settings, "embedding_provider", "mock")
    if provider in ("", "mock"):
        return MockHashEmbedding(getattr(settings, "embedding_dim", 256))
    if provider in ("openai", "openai-compatible"):
        return OpenAIEmbedding(
            base_url=getattr(settings, "openai_base_url", ""),
            api_key=getattr(settings, "openai_api_key", ""),
            model=getattr(settings, "embedding_model", "text-embedding-3-small"),
        )
    raise ValueError(f"未知的 Embedding Provider：{provider}")
