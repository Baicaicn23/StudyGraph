"use client";

import { useCallback, useEffect, useState } from "react";

import {
  listMemories,
  studyPlan,
  usage,
  type StudyPlan,
  type UsageSummary,
} from "@/lib/api";

export default function PlanPage() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [tokens, setTokens] = useState<UsageSummary | null>(null);
  const [memories, setMemories] = useState<string[]>([]);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextPlan, nextUsage, nextMemories] = await Promise.all([
        studyPlan(),
        usage(1),
        listMemories(),
      ]);
      setPlan(nextPlan);
      setTokens(nextUsage);
      setMemories(nextMemories);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold">今日复习</h1>
          <p className="mt-1 text-sm text-zinc-500">
            汇总到期题、薄弱学科与近期误区，给出「今天先做什么」。
          </p>
        </header>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">今天做什么</h2>
          {!plan ? (
            <p className="text-sm text-zinc-400">加载中…</p>
          ) : (
            <ul className="space-y-2">
              {plan.suggestions.map((item) => (
                <li
                  key={item}
                  className="rounded-lg bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-800"
                >
                  {item}
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="grid gap-6 sm:grid-cols-3">
          <Stat label="到期练习" value={plan ? plan.due_questions.length : "—"} />
          <Stat
            label="薄弱学科"
            value={plan ? plan.weak_libraries.length : "—"}
          />
          <Stat
            label="近 7 天误区"
            value={plan ? plan.recent_mistakes : "—"}
          />
        </div>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">学科掌握度</h2>
          {!plan || plan.weak_libraries.length === 0 ? (
            <p className="text-sm text-zinc-400">暂无数据。</p>
          ) : (
            <ul className="space-y-3">
              {plan.weak_libraries.map((item) => (
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

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">它记得关于你的（长期记忆）</h2>
          {memories.length === 0 ? (
            <p className="text-sm text-zinc-400">
              还没有。在聊天里说「记住：…」试试。
            </p>
          ) : (
            <ul className="space-y-1 text-sm">
              {memories.map((item) => (
                <li key={item}>· {item}</li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">今日 token 用量</h2>
          {!tokens ? (
            <p className="text-sm text-zinc-400">加载中…</p>
          ) : (
            <>
              <div className="text-2xl font-semibold">
                {tokens.total_tokens.toLocaleString()}
              </div>
              {tokens.by_model.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-zinc-500">
                  {tokens.by_model.map((item) => (
                    <li key={item.model}>
                      {item.model}：{item.total_tokens.toLocaleString()} tokens ·{" "}
                      {item.calls} 次调用
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
