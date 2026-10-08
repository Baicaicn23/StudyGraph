"use client";

import { useCallback, useEffect, useState } from "react";

import {
  addFeedback,
  generatePractice,
  listFeedback,
  listLibraries,
  type Feedback,
  type Library,
  type Question,
} from "@/lib/api";

export default function MistakesPage() {
  const [items, setItems] = useState<Feedback[]>([]);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [generated, setGenerated] = useState<Question[]>([]);
  const [library, setLibrary] = useState("");
  const [question, setQuestion] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [feedback, bases] = await Promise.all([
        listFeedback(),
        listLibraries(),
      ]);
      setItems(feedback);
      setLibraries(bases);
      setLibrary((current) => current || bases[0]?.name || "");
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const onAdd = async () => {
    setError("");
    setMessage("");
    if (!note.trim()) {
      setError("请至少写下你的误区内容");
      return;
    }
    try {
      await addFeedback(library.trim(), question.trim(), note.trim());
      setMessage("已记录");
      setQuestion("");
      setNote("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onGenerate = async (item: Feedback) => {
    setError("");
    setMessage("");
    setGenerated([]);
    try {
      const questions = await generatePractice("mistakes", item.library, 3);
      setGenerated(questions);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold">错题本</h1>
          <p className="mt-1 text-sm text-zinc-500">
            记下理解误区；之后可以让它**针对这个知识点**出新题。
          </p>
        </header>

        {message && (
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            {message}
          </p>
        )}
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">记录一条误区</h2>
          <div className="flex flex-col gap-3">
            <input
              value={library}
              onChange={(event) => setLibrary(event.target.value)}
              list="mistake-libraries"
              placeholder="学科（例如：线性代数）"
              className={inputClass}
            />
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="当时的问题（可选）"
              className={inputClass}
            />
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
              placeholder="你卡在哪 / 搞混了什么"
              className={inputClass}
            />
            <button type="button" onClick={() => void onAdd()} className={buttonClass}>
              记录
            </button>
          </div>
          <datalist id="mistake-libraries">
            {libraries.map((item) => (
              <option key={item.name} value={item.name} />
            ))}
          </datalist>
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-3 text-sm font-medium">我的误区（{items.length}）</h2>
          {items.length === 0 ? (
            <p className="text-sm text-zinc-400">还没有记录。</p>
          ) : (
            <ul className="space-y-3">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                      {item.library || "未标学科"}
                    </span>
                    <button
                      type="button"
                      onClick={() => void onGenerate(item)}
                      disabled={!item.library}
                      className="text-xs text-zinc-500 hover:text-zinc-900 disabled:opacity-40"
                    >
                      用它出题
                    </button>
                  </div>
                  {item.question && (
                    <p className="text-sm text-zinc-500">{item.question}</p>
                  )}
                  <p className="text-sm">{item.note}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        {generated.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-3 text-sm font-medium">针对误区的练习题</h2>
            <ul className="space-y-2">
              {generated.map((q) => (
                <li
                  key={q.id}
                  className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700"
                >
                  <div className="mb-1 text-xs text-zinc-500">
                    {q.library} · 来自你的误区
                  </div>
                  <p className="whitespace-pre-wrap">{q.prompt}</p>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-zinc-400">
              到「练习复习」页的自评区可继续作答。
            </p>
          </section>
        )}
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950";
const buttonClass =
  "self-start rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90 dark:bg-zinc-100 dark:text-zinc-900";
