"""评测命令行（门禁）。

    studygraph-eval retrieval --dataset evals/datasets/retrieval.json \
        --baseline evals/baselines/retrieval.json [--update]
    studygraph-eval intent --dataset evals/datasets/intent.json \
        --baseline evals/baselines/intent.json [--update]

有基线且指标掉超过容差时**退出码为 1**（可直接进 CI）。`--update` 覆盖基线。
检索评测强制用确定性 Mock 向量，保证同一版本任何人跑出同样的分数。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from ..application import evaluation as evals
from ..config import get_settings
from ..infrastructure.embeddings import MockHashEmbedding
from ..infrastructure.knowledge import KnowledgeStore


def _run_retrieval(args: argparse.Namespace) -> int:
    documents, cases, k = evals.load_retrieval_dataset(args.dataset)
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp:
        store = KnowledgeStore(
            Path(tmp) / "eval.db",
            embedder=MockHashEmbedding(settings.embedding_dim),
        )
        evals.seed_knowledge(store, documents)
        metrics = evals.run_retrieval_eval(store, cases, k=k)
    return _report("retrieval", metrics, args)


def _run_intent(args: argparse.Namespace) -> int:
    cases = evals.load_intent_dataset(args.dataset)
    metrics = evals.run_intent_eval(cases)
    return _report("intent", metrics, args)


def _report(kind: str, metrics: dict, args: argparse.Namespace) -> int:
    print(f"== {kind} 评测 ==")
    for key, value in metrics.items():
        if key == "misclassified":
            continue
        print(f"  {key}: {value}")

    if args.update:
        Path(args.baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.baseline).write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"  已写入基线：{args.baseline}")
        return 0

    baseline = evals.load_baseline(args.baseline)
    if not baseline:
        print("  （无基线，未做回归比对；用 --update 生成）")
        return 0

    regressions = evals.compare_to_baseline(metrics, baseline, tolerance=args.tolerance)
    if regressions:
        print("  ✗ 回归：")
        for item in regressions:
            print(f"    - {item}")
        return 1
    print("  ✓ 无回归")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studygraph-eval", description="StudyGraph 评测")
    sub = parser.add_subparsers(dest="command", required=True)

    retrieval = sub.add_parser("retrieval", help="检索 Hit@K / MRR 评测")
    retrieval.add_argument("--dataset", required=True)
    retrieval.add_argument("--baseline", required=True)
    retrieval.add_argument("--tolerance", type=float, default=0.05)
    retrieval.add_argument("--update", action="store_true")
    retrieval.set_defaults(func=_run_retrieval)

    intent = sub.add_parser("intent", help="意图分类准确率评测")
    intent.add_argument("--dataset", required=True)
    intent.add_argument("--baseline", required=True)
    intent.add_argument("--tolerance", type=float, default=0.05)
    intent.add_argument("--update", action="store_true")
    intent.set_defaults(func=_run_intent)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
