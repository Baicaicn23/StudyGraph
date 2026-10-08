from __future__ import annotations

from pathlib import Path

from studygraph.application import evaluation as evals
from studygraph.domain.evaluation import hit_at_k, mean, reciprocal_rank
from studygraph.infrastructure.knowledge import KnowledgeStore


def test_retrieval_metric_functions() -> None:
    gold = {"导数"}
    assert hit_at_k(["导数", "积分"], gold, 1) == 1.0
    assert hit_at_k(["积分", "导数"], gold, 1) == 0.0
    assert hit_at_k(["积分", "导数"], gold, 2) == 1.0
    assert reciprocal_rank(["积分", "导数"], gold) == 0.5
    assert reciprocal_rank(["积分"], gold) == 0.0
    assert mean([1.0, 0.0]) == 0.5


def test_run_retrieval_eval_scores_perfect_on_matching_corpus(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "eval.db")
    evals.seed_knowledge(
        store,
        [
            {"library": "高等数学", "title": "导数", "content": "导数是瞬时变化率，反映切线斜率。"},
            {"library": "线性代数", "title": "秩", "content": "矩阵的秩是非零行的数目。"},
        ],
    )
    cases = [
        evals.RetrievalCase(query="导数是瞬时变化率吗", gold_titles={"导数"}),
        evals.RetrievalCase(query="非零行的数目", gold_titles={"秩"}),
    ]

    metrics = evals.run_retrieval_eval(store, cases, k=3)

    assert metrics["hit_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["cases"] == 2


def test_run_intent_eval_reports_accuracy_and_errors() -> None:
    from studygraph.application.routing import CALCULATION

    cases = [
        evals.IntentCase(text="帮我算一下 37 * 43", intent=CALCULATION),
        evals.IntentCase(text="你好呀", intent="not_real_intent"),
    ]
    metrics = evals.run_intent_eval(cases)
    assert metrics["accuracy"] == 0.5
    assert metrics["misclassified"]


def test_compare_to_baseline_flags_regressions_with_tolerance() -> None:
    baseline = {"mrr": 1.0, "cases": 6}
    assert evals.compare_to_baseline({"mrr": 1.0}, baseline) == []
    assert evals.compare_to_baseline({"mrr": 0.98}, baseline) == []  # 容差内
    regressions = evals.compare_to_baseline({"mrr": 0.7}, baseline)
    assert regressions and "mrr" in regressions[0]
