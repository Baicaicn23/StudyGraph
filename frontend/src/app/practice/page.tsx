"use client";

import { useCallback, useEffect, useState } from "react";

import {
  answerQuestion,
  dueQuestions,
  generatePractice,
  listLibraries,
  studyPlan,
  type AnswerResult,
  type Library,
  type PracticeRating,
  type PracticeSource,
  type Question,
  type WeakLibrary,
} from "@/lib/api";

const RATINGS: { value: PracticeRating; label: string }[] = [
  { value: "again", label: "又忘了" },
  { value: "hard", label: "有点难" },
  { value: "good", label: "掌握了" },
  { value: "easy", label: "太简单" },
];

export default function PracticePage() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [source, setSource] = useState<PracticeSource>("knowledge_base");
  const [library, setLibrary] = useState("");
  const [count, setCount] = useState(3);
  const [generated, setGenerated] = useState<Question[]>([]);
  const [queue, setQueue] = useState<Question[]>([]);
  const [weak, setWeak] = useState<WeakLibrary[]>([]);
  const [results, setResults] = useState<Record<number, AnswerResult>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [bases, due, plan] = await Promise.all([
        listLibraries(),
        dueQuestions(),
        studyPlan(),
      ]);
      setLibraries(bases);
      setQueue(due);
      setWeak(plan.weak_libraries);
      setLibrary((current) => current || bases[0]?.name || "");
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const onGenerate = async () => {
    setBusy(true);
    setError("");
    try {
      const questions = await generatePractice(
        source,
        source === "knowledge_base" ? library : "",
        count,
      );
      setGenerated(questions);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
      setGenerated([]);
    } finally {
      setBusy(false);
    }
  };

  const onAnswer = async (questionId: number, rating: PracticeRating) => {
    setError("");
    try {
      const result = await answerQuestion(questionId, rating);
      setResults((prev) => ({ ...prev, [questionId]: result }));
      setQueue((prev) => prev.filter((q) => q.id !== questionId));
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold">练习与复习</h1>
          <p className="mt-1 text-sm text-zinc-500">
            出题 → 自评 → 掌握度与下次复习时间自动更新（间隔重复）。
          </p>
        </header>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">生成练习题</h2>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-500">
              出题来源
              <select
                value={source}
                onChange={(event) =>
                  setSource(event.target.value as PracticeSource)
                }
                className={`mt-1 block ${selectClass}`}
              >
                <option value="knowledge_base">来自知识库</option>
                <option value="mistakes">来自我的错题</option>
              </select>
            </label>
            {source === "knowledge_base" && (
              <label className="text-xs text-zinc-500">
                知识库
                <select
                  value={library}
                  onChange={(event) => setLibrary(event.target.value)}
                  className={`mt-1 block ${selectClass}`}
                >
                  {libraries.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name} · {item.document_count}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="text-xs text-zinc-500">
              数量
              <select
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                className={`mt-1 block ${selectClass}`}
              >
                {[1, 2, 3, 5].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void onGenerate()}
              disabled={busy || (source === "knowledge_base" && !library)}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {busy ? "生成中…" : "生成"}
            </button>
          </div>

          {generated.length > 0 && (
            <ul className="mt-4 space-y-2">
              {generated.map((question) => (
                <li
                  key={question.id}
                  className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700"
                >
                  <div className="mb-1 flex items-center gap-2 text-xs text-zinc-500">
                    <span className="rounded bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">
                      {question.library}
                    </span>
                    {question.source === "mistake" && (
                      <span className="rounded border border-zinc-300 px-2 py-0.5 dark:border-zinc-600">
                        来自你的误区
                      </span>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap">{question.prompt}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">
            今日待复习（{queue.length}）
          </h2>
          {queue.length === 0 ? (
            <p className="text-sm text-zinc-400">暂无到期题目。去上面生成几道吧。</p>
          ) : (
            <ul className="space-y-4">
              {queue.map((question) => (
                <li key={question.id} className="space-y-2">
                  <div className="text-xs text-zinc-500">{question.library}</div>
                  <p className="whitespace-pre-wrap text-sm">{question.prompt}</p>
                  <textarea
                    rows={2}
                    placeholder="写下你的作答（自评用，不会提交）…"
                    className="w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                  <div className="flex flex-wrap gap-2">
                    {RATINGS.map((rating) => (
                      <button
                        key={rating.value}
                        type="button"
                        onClick={() => void onAnswer(question.id, rating.value)}
                        className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                      >
                        {rating.label}
                      </button>
                    ))}
                  </div>
                  {results[question.id] && (
                    <p className="text-xs text-emerald-600 dark:text-emerald-400">
                      掌握度 {results[question.id].mastery}% ·{" "}
                      {results[question.id].due_in_days > 0
                        ? `${results[question.id].due_in_days} 天后复习`
                        : "稍后再来"}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">学科掌握度</h2>
          {weak.length === 0 ? (
            <p className="text-sm text-zinc-400">还没有掌握度数据，先做几道题。</p>
          ) : (
            <ul className="space-y-3">
              {weak.map((item) => (
                <li key={item.library}>
                  <div className="mb-1 flex justify-between text-xs text-zinc-500">
                    <span>{item.library}</span>
                    <span>{item.mastery}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800">
                    <div
                      className="h-2 rounded-full bg-zinc-900 dark:bg-zinc-100"
                      style={{ width: `${Math.min(100, item.mastery)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

const selectClass =
  "rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
