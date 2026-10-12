"""在线/离线评测的用例编排。

- 检索评测：把固定语料灌进知识库，跑固定问题，算 Hit@K / MRR。
- 意图评测：跑固定标注句，算规则分类准确率。
- 基线对比：与存下来的基线比，掉超过容差就是**回归**（用于 CI 门禁）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..domain.evaluation import hit_at_k, mean, reciprocal_rank
from .ports import KnowledgePort
from .routing import classify


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    gold_titles: set[str]


@dataclass(frozen=True)
class IntentCase:
    text: str
    intent: str


def load_retrieval_dataset(
    path: str | Path,
) -> tuple[list[dict[str, str]], list[RetrievalCase], int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    documents = payload["documents"]
    cases = [
        RetrievalCase(query=item["query"], gold_titles=set(item["gold_titles"]))
        for item in payload["cases"]
    ]
    return documents, cases, int(payload.get("k", 3))


def load_intent_dataset(path: str | Path) -> list[IntentCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [IntentCase(text=item["text"], intent=item["intent"]) for item in payload]


def seed_knowledge(knowledge: KnowledgePort, documents: list[dict[str, str]]) -> None:
    for document in documents:
        knowledge.add_document(
            document["library"], document["title"], document["content"]
        )


def run_retrieval_eval(
    knowledge: KnowledgePort, cases: list[RetrievalCase], *, k: int
) -> dict[str, object]:
    rankings: list[list[str]] = []
    for case in cases:
        hits = knowledge.search(case.query, limit=max(k, 8))
        rankings.append([hit.title for hit in hits])
    hit_scores = [
        hit_at_k(ranking, case.gold_titles, k)
        for ranking, case in zip(rankings, cases, strict=True)
    ]
    rr_scores = [
        reciprocal_rank(ranking, case.gold_titles)
        for ranking, case in zip(rankings, cases, strict=True)
    ]
    return {
        "cases": len(cases),
        "k": k,
        "hit_at_k": mean(hit_scores),
        "mrr": mean(rr_scores),
    }


def run_intent_eval(cases: list[IntentCase]) -> dict[str, object]:
    misclassified: list[dict[str, str]] = []
    correct = 0
    for case in cases:
        predicted, _confidence = classify(case.text)
        if predicted == case.intent:
            correct += 1
        else:
            misclassified.append(
                {"text": case.text, "expected": case.intent, "got": predicted}
            )
    accuracy = round(correct / len(cases), 4) if cases else 0.0
    return {"cases": len(cases), "accuracy": accuracy, "misclassified": misclassified}


def load_baseline(path: str | Path) -> dict:
    file = Path(path)
    if not file.exists():
        return {}
    return json.loads(file.read_text(encoding="utf-8"))


def compare_to_baseline(
    metrics: dict[str, object], baseline: dict, *, tolerance: float = 0.05
) -> list[str]:
    """挑出比基线掉超过容差的指标（回归）。只比较数值指标，忽略 case 数等。"""

    regressions: list[str] = []
    for key, base in baseline.items():
        if key in {"cases", "k", "misclassified"}:
            continue
        value = metrics.get(key)
        if isinstance(base, (int, float)) and isinstance(value, (int, float)):
            if value < float(base) - tolerance:
                regressions.append(
                    f"{key}: {value} < 基线 {base}（容差 {tolerance}）"
                )
    return regressions
