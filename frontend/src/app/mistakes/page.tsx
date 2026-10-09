"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addFeedback,
  deleteFeedback,
  generatePractice,
  listFeedback,
  listLibraries,
  type Feedback,
  type Library,
  type Question,
} from "@/lib/api";
import { buttonClass, Card, inputClass, Notice, Page, selectClass } from "@/components/ui";

const QUICK_TAGS = ["概念混淆", "公式记错", "计算错误"];

function relativeDay(timestamp: number): string {
  const diff = Date.now() / 1000 - timestamp;
  if (diff < 86400) return "今天";
  if (diff < 2 * 86400) return "昨天";
  return `${Math.floor(diff / 86400)} 天前`;
}

export default function MistakesPage() {
  const [items, setItems] = useState<Feedback[]>([]);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [generated, setGenerated] = useState<Question[]>([]);
  const [library, setLibrary] = useState("");
  const [question, setQuestion] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [generatingId, setGeneratingId] = useState<number | null>(null);

  // 筛选与搜索
  const [filterLibrary, setFilterLibrary] = useState("");
  const [search, setSearch] = useState("");
  // 长内容展开
  const [expanded, setExpanded] = useState<number[]>([]);

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
    setSaving(true);
    try {
      await addFeedback(library.trim(), question.trim(), note.trim());
      setMessage("已记录");
      setQuestion("");
      setNote("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (item: Feedback) => {
    const ok = window.confirm("确定删除这条误区记录吗？");
    if (!ok) return;
    try {
      await deleteFeedback(item.id);
      setExpanded((prev) => prev.filter((id) => id !== item.id));
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onGenerate = async (item: Feedback) => {
    setError("");
    setMessage("");
    setGenerated([]);
    setGeneratingId(item.id);
    try {
      const questions = await generatePractice("mistakes", item.library, 3);
      setGenerated(questions);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGeneratingId(null);
    }
  };

  // 学科筛选选项：学科库 ∪ 已有误区标注过的学科
  const libraryOptions = useMemo(() => {
    const names = new Set(libraries.map((item) => item.name));
    items.forEach((item) => {
      if (item.library) names.add(item.library);
    });
    return [...names].sort((a, b) => a.localeCompare(b, "zh"));
  }, [libraries, items]);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return items.filter((item) => {
      if (filterLibrary && item.library !== filterLibrary) return false;
      if (!keyword) return true;
      return `${item.question} ${item.note}`.toLowerCase().includes(keyword);
    });
  }, [items, filterLibrary, search]);

  const toggleExpand = (id: number) =>
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );

  const appendQuickTag = (tag: string) => {
    const current = note.trim();
    if (current.includes(tag)) return;
    setNote(current ? `${current}，${tag}` : tag);
  };

  return (
    <Page
      wide
      title="错题本"
      subtitle="记下理解误区；之后可以让它针对这个知识点出新题。"
    >
      {message && <Notice kind="ok">{message}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]">
        {/* 左主栏：我的误区（65%，独立滚动 + 筛选吸顶） */}
        <section className="flex max-h-[calc(100dvh-150px)] flex-col overflow-hidden rounded-xl bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] lg:sticky lg:top-0">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              我的误区
              <span className="rounded-full bg-black/[0.05] px-2 py-0.5 text-[11px] font-medium tabular-nums text-zinc-500">
                {items.length}
              </span>
            </h2>
          </div>

          {/* 筛选行 */}
          <div className="mt-3 flex gap-2">
            <select
              value={filterLibrary}
              onChange={(event) => setFilterLibrary(event.target.value)}
              className="w-36 shrink-0 rounded-xl bg-white px-2.5 py-1.5 text-xs text-zinc-600 ring-1 ring-black/10 outline-none transition focus:ring-2 focus:ring-teal-600"
              aria-label="按学科筛选"
            >
              <option value="">全部学科</option>
              {libraryOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <div className="relative min-w-0 flex-1">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索误区关键词…"
                className="w-full rounded-xl bg-white py-1.5 pl-8 pr-3 text-xs ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
              />
            </div>
          </div>

          {/* 列表（独立滚动） */}
          <div className="mt-3 flex-1 space-y-3 overflow-y-auto pr-0.5">
            {items.length === 0 ? (
              <div className="py-14 text-center">
                <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-xl bg-black/[0.04] text-zinc-400">
                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                    <path d="M14 2v6h6M16 13H8M16 17H8" />
                  </svg>
                </div>
                <p className="mt-2.5 text-sm font-medium text-zinc-600">
                  还没有误区记录
                  <span className="font-normal text-zinc-400">
                    ，右侧记下第一条吧
                  </span>
                </p>
                <Link
                  href="/practice"
                  className="mt-1.5 inline-block text-xs font-semibold text-teal-700 underline-offset-2 hover:underline"
                >
                  去练习生成错题 →
                </Link>
              </div>
            ) : filtered.length === 0 ? (
              <p className="py-10 text-center text-sm text-zinc-400">
                没有匹配的误区，换个筛选条件试试。
              </p>
            ) : (
              filtered.map((item) => {
                const isExpanded = expanded.includes(item.id);
                const longNote = item.note.length > 80;
                const noteText =
                  longNote && !isExpanded
                    ? `${item.note.slice(0, 80)}…`
                    : item.note;
                return (
                  <div
                    key={item.id}
                    className="animate-fade-up rounded-xl border border-black/[0.06] bg-black/[0.02] p-4 transition-all duration-200 hover:-translate-y-px hover:bg-black/[0.03] hover:shadow-[0_2px_10px_rgba(0,0,0,0.06)]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-black/[0.05] px-2.5 py-0.5 text-[11px] font-medium leading-4 text-zinc-600">
                        {item.library || "未标学科"}
                      </span>
                      <span className="ml-auto text-[10px] text-zinc-300">
                        {relativeDay(item.created_at)}
                      </span>
                      <button
                        type="button"
                        onClick={() => void onDelete(item)}
                        title="删除这条误区"
                        className="grid h-6 w-6 place-items-center rounded-md text-zinc-300 transition hover:bg-red-50 hover:text-red-600 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                          <path d="M3 6h18" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                          <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={() => void onGenerate(item)}
                        disabled={!item.library || generatingId !== null}
                        className="text-xs font-medium text-teal-700 transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40"
                      >
                        {generatingId === item.id ? "出题中…" : "用它出题"}
                      </button>
                    </div>
                    {item.question && (
                      <p className="mt-2 text-sm leading-relaxed text-zinc-700">
                        {item.question}
                      </p>
                    )}
                    <div className="mt-2 rounded-lg bg-red-50/70 p-3">
                      <p className="text-xs font-semibold text-red-600">
                        核心误区
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-red-900/80">
                        {noteText}
                      </p>
                      {longNote && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(item.id)}
                          className="mt-1 text-[11px] font-medium text-zinc-400 transition hover:text-zinc-600"
                        >
                          {isExpanded ? "收起" : "展开全文"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* 右副栏：记录表单 + 出题结果（35%） */}
        <div className="space-y-6">
          <Card title="记录一条误区">
            <div className="flex flex-col gap-3.5">
              <label className="block text-[11px] text-zinc-400">
                学科
                <select
                  value={library}
                  onChange={(event) => setLibrary(event.target.value)}
                  className={`mt-1 block w-full ${selectClass}`}
                >
                  {libraryOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-[11px] text-zinc-400">
                当时的问题
                <span className="ml-1 text-zinc-300">可选</span>
                <input
                  value={question}
                  maxLength={4000}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="例如：定积分和不定积分有什么区别？"
                  className={`mt-1 block w-full ${inputClass}`}
                />
              </label>
              <label className="block text-[11px] text-zinc-400">
                你卡在哪 / 搞混了什么
                <textarea
                  value={note}
                  maxLength={2000}
                  onChange={(event) => setNote(event.target.value)}
                  rows={4}
                  placeholder="例：我把定积分的结果当成了带常数 C 的函数…"
                  className={`mt-1 block w-full ${inputClass}`}
                />
              </label>
              {/* 常用误区快捷标签 */}
              <div className="flex flex-wrap gap-1.5">
                {QUICK_TAGS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => appendQuickTag(tag)}
                    className="rounded-full bg-black/[0.04] px-2.5 py-1 text-[11px] text-zinc-600 transition hover:bg-[#0f766e] hover:text-white focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    {tag}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => void onAdd()}
                disabled={saving}
                className={`${buttonClass} w-full`}
              >
                {saving ? "记录中…" : "记录"}
              </button>
            </div>
          </Card>

          {generated.length > 0 && (
            <Card title="针对误区的练习题">
              <ul className="space-y-2.5">
                {generated.map((q) => (
                  <li
                    key={q.id}
                    className="animate-fade-up rounded-xl bg-black/[0.03] p-4 text-sm"
                  >
                    <div className="mb-1.5 text-xs font-medium text-zinc-500">
                      {q.library} · 来自你的误区
                    </div>
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {q.prompt}
                    </p>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-zinc-400">
                到「练习复习」页的自评区可继续作答。
              </p>
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}
