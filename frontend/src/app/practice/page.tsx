"use client";

// 错题练习（一个入口两个 tab）：
//   ① 错题本：沉淀 + 智能分类（按错误类型聚合）+ 每条一键「出变式题」
//   ② 专项练习：挑错题（或换知识库）→ 流式生成 → 牌堆复习（自评后卡片飞出）
// 旧入口 /mistakes 重定向到这里的第一 tab。

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  addFeedback,
  answerQuestion,
  deleteFeedback,
  deleteQuestion,
  dueQuestions,
  generatePracticeStream,
  listFeedback,
  listLibraries,
  studyPlan,
  type AnswerResult,
  type Feedback,
  type GenerateProgress,
  type Library,
  type PracticeDifficulty,
  type PracticeRating,
  type Question,
  type WeakLibrary,
} from "@/lib/api";
import { Card, Notice, Page, selectClass } from "@/components/ui";

/* ---------- 常量 ---------- */

const RATINGS: { value: PracticeRating; label: string; cls: string }[] = [
  {
    value: "again",
    label: "又忘了",
    cls: "border-red-200 text-red-600 hover:bg-red-50 active:border-red-500 active:bg-red-500 active:text-white",
  },
  {
    value: "hard",
    label: "有点难",
    cls: "border-zinc-300 text-zinc-600 hover:bg-zinc-100 active:border-zinc-600 active:bg-zinc-600 active:text-white",
  },
  {
    value: "good",
    label: "掌握了",
    cls: "border-teal-300 text-teal-700 hover:bg-teal-50 active:border-teal-600 active:bg-teal-600 active:text-white",
  },
  {
    value: "easy",
    label: "太简单",
    cls: "border-teal-600 bg-teal-600 text-white shadow-sm hover:bg-teal-700",
  },
];

const DIFFICULTY_TAGS: Record<string, { label: string; cls: string }> = {
  basic: { label: "基础", cls: "bg-black/[0.05] text-zinc-600" },
  apply: { label: "进阶", cls: "bg-teal-600/10 text-teal-700" },
  transfer: { label: "迁移", cls: "bg-amber-500/10 text-amber-700" },
};

/** 误区错误类型：与"哪个学科"正交的"为什么错"。 */
const MISTAKE_KINDS: { value: string; label: string }[] = [
  { value: "concept", label: "概念混淆" },
  { value: "step", label: "步骤遗漏" },
  { value: "condition", label: "条件误读" },
  { value: "calc", label: "计算失误" },
  { value: "wording", label: "表述不清" },
];

const KIND_LABELS: Record<string, string> = Object.fromEntries(
  MISTAKE_KINDS.map((item) => [item.value, item.label]),
);

const STAR_KEY = "studygraph-starred-questions";
const MISTAKE_MARKER = "【你当时记下的误区】";

function relativeDay(timestamp: number): string {
  const diff = Date.now() / 1000 - timestamp;
  if (diff < 86400) return "今天";
  if (diff < 2 * 86400) return "昨天";
  return `${Math.floor(diff / 86400)} 天前`;
}

function DifficultyTag({ difficulty }: { difficulty?: string }) {
  if (!difficulty) return null;
  const tag = DIFFICULTY_TAGS[difficulty];
  if (!tag) return null;
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium leading-4 ${tag.cls}`}
    >
      {tag.label}
    </span>
  );
}

/** 错题模板的题干自带误区标记，按标记拆成「正文 + 误区」两段渲染。 */
function splitMistake(prompt: string): { main: string; note: string | null } {
  const index = prompt.indexOf(MISTAKE_MARKER);
  if (index === -1) return { main: prompt, note: null };
  return {
    main: prompt.slice(0, index).replace("【当时的问题】", "").trim(),
    note: prompt.slice(index + MISTAKE_MARKER.length).trim(),
  };
}

/** 题面：标签行 + 题干 + 误区块（牌堆当前牌与飞走牌共用）。 */
function QuestionBody({ question }: { question: Question }) {
  const { main, note } = splitMistake(question.prompt);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-black/[0.05] px-2.5 py-0.5 text-[11px] font-medium leading-4 text-zinc-600">
          {question.library}
        </span>
        {question.source === "mistake" && (
          <span className="rounded-full bg-red-100/80 px-2.5 py-0.5 text-[11px] font-medium leading-4 text-red-700">
            来自你的误区
          </span>
        )}
        <DifficultyTag difficulty={question.difficulty} />
      </div>
      <p className="mt-4 whitespace-pre-wrap text-[15px] leading-[2.05] text-zinc-900">
        {main}
      </p>
      {note && (
        <div className="mt-3 rounded-xl bg-red-50/70 p-3.5">
          <p className="text-xs font-semibold text-red-600">
            你当时记下的误区
          </p>
          <p className="mt-1 text-sm leading-relaxed text-red-900/80">{note}</p>
        </div>
      )}
    </>
  );
}

/* ---------- 页面外壳：tab + 跨 tab 传参 ---------- */

export default function PracticePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center bg-white">
          <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-200 border-t-teal-600" />
        </div>
      }
    >
      <PracticeInner />
    </Suspense>
  );
}

function PracticeInner() {
  const params = useSearchParams();
  const [tab, setTab] = useState<"mistakes" | "practice">(
    params.get("tab") === "mistakes" ? "mistakes" : "practice",
  );
  // 错题本点「出变式题」→ 带着选中的错题跳到专项练习
  const [preselected, setPreselected] = useState<number[]>([]);

  const jumpToPractice = useCallback((ids: number[]) => {
    setPreselected(ids);
    setTab("practice");
  }, []);

  return (
    <Page
      wide
      title="错题练习"
      subtitle="先把错因写清楚，再针对它出变式题——练到会为止。"
    >
      <div className="flex items-center gap-1.5">
        {(
          [
            { key: "mistakes" as const, label: "错题本" },
            { key: "practice" as const, label: "专项练习" },
          ]
        ).map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`rounded-full px-4 py-1.5 text-[13px] transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
              tab === item.key
                ? "bg-teal-600 font-medium text-white shadow-sm"
                : "text-zinc-500 hover:bg-black/[0.04] hover:text-zinc-800"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "mistakes" ? (
        <MistakesTab onSendToPractice={jumpToPractice} />
      ) : (
        <PracticeTab
          preselected={preselected}
          onConsumePreselect={() => setPreselected([])}
        />
      )}
    </Page>
  );
}

/* ---------- Tab 1：错题本（沉淀 + 智能分类） ---------- */

function MistakesTab({
  onSendToPractice,
}: {
  onSendToPractice: (ids: number[]) => void;
}) {
  const [items, setItems] = useState<Feedback[]>([]);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  // 记录表单
  const [library, setLibrary] = useState("");
  const [question, setQuestion] = useState("");
  const [note, setNote] = useState("");
  const [kind, setKind] = useState("");
  const [saving, setSaving] = useState(false);
  // 筛选
  const [filterKind, setFilterKind] = useState("");
  const [filterLibrary, setFilterLibrary] = useState("");
  const [search, setSearch] = useState("");
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
      await addFeedback(library.trim(), question.trim(), note.trim(), kind);
      setMessage("已记录，可在上方分类里看到它");
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
    if (!window.confirm("确定删除这条误区记录吗？")) return;
    try {
      await deleteFeedback(item.id);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const libraryOptions = useMemo(() => {
    const names = new Set(libraries.map((item) => item.name));
    items.forEach((item) => {
      if (item.library) names.add(item.library);
    });
    return [...names].sort((a, b) => a.localeCompare(b, "zh"));
  }, [libraries, items]);

  /** 智能分类：按错误类型聚合（纯统计，零模型调用） */
  const kindStats = useMemo(() => {
    const stats = new Map<
      string,
      { total: number; libraries: Map<string, number> }
    >();
    items.forEach((item) => {
      const key = item.kind && KIND_LABELS[item.kind] ? item.kind : "";
      const entry =
        stats.get(key) ?? { total: 0, libraries: new Map<string, number>() };
      entry.total += 1;
      const label = item.library || "未标学科";
      entry.libraries.set(label, (entry.libraries.get(label) ?? 0) + 1);
      stats.set(key, entry);
    });
    return [...stats.entries()]
      .sort((a, b) => b[1].total - a[1].total)
      .map(([key, entry]) => ({
        key,
        label: key ? KIND_LABELS[key] : "未分类",
        total: entry.total,
        breakdown: [...entry.libraries.entries()]
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([name, count]) => `${name} ${count}`)
          .join(" · "),
      }));
  }, [items]);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return items.filter((item) => {
      if (filterKind !== "" && (item.kind ?? "") !== filterKind) return false;
      if (filterLibrary && item.library !== filterLibrary) return false;
      if (!keyword) return true;
      return `${item.question} ${item.note}`.toLowerCase().includes(keyword);
    });
  }, [items, filterKind, filterLibrary, search]);

  const hasFilter = Boolean(filterKind || filterLibrary || search);

  return (
    <div className="space-y-6">
      {message && <Notice kind="ok">{message}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={filterLibrary}
          onChange={(event) => setFilterLibrary(event.target.value)}
          className="w-32 rounded-xl bg-white px-2.5 py-1.5 text-xs text-zinc-600 ring-1 ring-black/10 outline-none focus:ring-2 focus:ring-teal-600"
          aria-label="按学科筛选"
        >
          <option value="">全部学科</option>
          {libraryOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="搜索误区关键词…"
          className="w-56 rounded-xl bg-white px-3 py-1.5 text-xs ring-1 ring-black/10 outline-none placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
        />
        {hasFilter && (
          <button
            type="button"
            onClick={() => {
              setFilterKind("");
              setFilterLibrary("");
              setSearch("");
            }}
            className="text-xs text-zinc-400 transition hover:text-zinc-600"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* 智能分类 */}
      {kindStats.length > 0 && (
        <div className="rounded-2xl bg-zinc-50 p-4 ring-1 ring-black/[0.05]">
          <div className="flex items-baseline justify-between">
            <span className="text-[13px] font-semibold text-zinc-800">
              智能分类
            </span>
            <span className="text-[11px] text-zinc-400">
              按错误类型聚合，点标签筛选
            </span>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {kindStats.map((stat) => (
              <button
                key={stat.label}
                type="button"
                onClick={() =>
                  setFilterKind((current) =>
                    current === stat.key ? "" : stat.key,
                  )
                }
                className={`rounded-xl bg-white px-3.5 py-3 text-left transition hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                  filterKind === stat.key
                    ? "ring-2 ring-teal-600/50"
                    : "ring-1 ring-black/[0.06]"
                }`}
              >
                <div className="text-[11px] text-zinc-500">{stat.label}</div>
                <div className="mt-0.5 text-xl font-bold tracking-tight tabular-nums text-zinc-800">
                  {stat.total}
                </div>
                {stat.breakdown && (
                  <div className="mt-1 truncate text-[10px] text-zinc-400">
                    {stat.breakdown}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]">
        {/* 误区列表 */}
        <div className="space-y-3">
          {items.length === 0 ? (
            <div className="rounded-2xl bg-white py-14 text-center ring-1 ring-black/[0.06]">
              <p className="text-sm font-medium text-zinc-600">
                还没有误区记录
                <span className="font-normal text-zinc-400">
                  ，右侧记下第一条吧
                </span>
              </p>
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
                  className="animate-fade-up rounded-2xl bg-white p-4 ring-1 ring-black/[0.06] transition hover:shadow-[0_1px_3px_rgba(0,0,0,0.05)]"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-black/[0.05] px-2.5 py-0.5 text-[11px] font-medium leading-4 text-zinc-600">
                      {item.library || "未标学科"}
                    </span>
                    {item.kind && KIND_LABELS[item.kind] && (
                      <span className="rounded-full bg-teal-600/10 px-2.5 py-0.5 text-[11px] font-medium leading-4 text-teal-700">
                        {KIND_LABELS[item.kind]}
                      </span>
                    )}
                    <span className="ml-auto text-[10px] text-zinc-400">
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
                  </div>
                  {item.question && (
                    <p className="mt-2.5 text-sm leading-relaxed text-zinc-800">
                      {item.question}
                    </p>
                  )}
                  <div className="mt-2.5 rounded-xl bg-red-50/70 p-3">
                    <p className="text-[11px] font-semibold text-red-600">
                      核心误区
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-red-900/80">
                      {noteText}
                    </p>
                    {longNote && (
                      <button
                        type="button"
                        onClick={() =>
                          setExpanded((prev) =>
                            prev.includes(item.id)
                              ? prev.filter((id) => id !== item.id)
                              : [...prev, item.id],
                          )
                        }
                        className="mt-1 text-[11px] font-medium text-zinc-400 transition hover:text-zinc-600"
                      >
                        {isExpanded ? "收起" : "展开全文"}
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => onSendToPractice([item.id])}
                    className="mt-3 text-xs font-medium text-teal-700 transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    出 3 道变式题 ›
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* 记录一条误区 */}
        <Card title="记一条误区">
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
                className="mt-1 block w-full rounded-xl bg-white px-3.5 py-2 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
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
                className="mt-1 block w-full resize-none rounded-xl bg-white px-3.5 py-2.5 text-sm leading-[1.8] ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
              />
            </label>
            <div>
              <span className="text-[11px] text-zinc-400">
                错误类型
                <span className="ml-1 text-zinc-300">可选，便于按类回炉</span>
              </span>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {MISTAKE_KINDS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() =>
                      setKind((current) =>
                        current === option.value ? "" : option.value,
                      )
                    }
                    className={`rounded-full px-2.5 py-1 text-[11px] transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                      kind === option.value
                        ? "bg-teal-600/10 font-medium text-teal-800 ring-1 ring-teal-600/40"
                        : "text-zinc-500 ring-1 ring-black/[0.08] hover:bg-black/[0.04]"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              type="button"
              onClick={() => void onAdd()}
              disabled={saving}
              className="w-full rounded-full bg-teal-600 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-40"
            >
              {saving ? "记录中…" : "记录"}
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ---------- Tab 2：专项练习（出题 + 牌堆复习） ---------- */

function PracticeTab({
  preselected,
  onConsumePreselect,
}: {
  preselected: number[];
  onConsumePreselect: () => void;
}) {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [mistakes, setMistakes] = useState<Feedback[]>([]);
  const [source, setSource] = useState<"mistakes" | "knowledge_base">("mistakes");
  const [pickedMistakes, setPickedMistakes] = useState<number[]>([]);
  const [library, setLibrary] = useState("");
  const [count, setCount] = useState(3);
  const [difficulty, setDifficulty] = useState<PracticeDifficulty>("auto");
  const [queue, setQueue] = useState<Question[]>([]);
  const [weak, setWeak] = useState<WeakLibrary[]>([]);
  const [results, setResults] = useState<Record<number, AnswerResult>>({});
  const [lastResult, setLastResult] = useState<
    (AnswerResult & { prompt: string }) | null
  >(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [genMsg, setGenMsg] = useState("");
  const [genProgress, setGenProgress] = useState<GenerateProgress | null>(null);
  const [starred, setStarred] = useState<number[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [flying, setFlying] = useState<{
    question: Question;
    result: AnswerResult;
  } | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const reviewRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [bases, due, plan, feedback] = await Promise.all([
        listLibraries(),
        dueQuestions(),
        studyPlan(),
        listFeedback(),
      ]);
      setLibraries(bases);
      setQueue(due);
      setWeak(plan.weak_libraries);
      setMistakes(feedback);
      setLibrary((current) => current || bases[0]?.name || "");
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    try {
      setStarred(JSON.parse(localStorage.getItem(STAR_KEY) ?? "[]") as number[]);
    } catch {
      setStarred([]);
    }
  }, [refresh]);

  // 从错题本带过来的选中错题：预勾选 + 每条的默认 3 道
  useEffect(() => {
    if (preselected.length === 0) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSource("mistakes");
    setPickedMistakes(preselected);
    setCount(Math.min(10, preselected.length * 3));
    onConsumePreselect();
  }, [preselected, onConsumePreselect]);

  const onGenerate = async () => {
    if (source === "mistakes" && pickedMistakes.length === 0) {
      setError("先在左侧挑几条要强化的错题");
      return;
    }
    if (source === "knowledge_base" && !library) {
      setError("请先选择知识库");
      return;
    }
    setBusy(true);
    setError("");
    setGenMsg("");
    setGenProgress(null);
    try {
      const questions = await generatePracticeStream(
        source,
        source === "knowledge_base" ? library : "",
        count,
        difficulty,
        (progress) => setGenProgress(progress),
        source === "mistakes" ? pickedMistakes : [],
      );
      if (questions.length === 0) {
        throw new Error("没有生成出题目，换几条错题或换个难度再试");
      }
      setGenMsg(`已生成 ${questions.length} 道题，已加入今日待复习`);
      await refresh();
      reviewRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      setGenProgress(null);
    }
  };

  const onAnswer = async (questionId: number, rating: PracticeRating) => {
    const question = queue.find((q) => q.id === questionId);
    if (!question || flying) return;
    setError("");
    try {
      const result = await answerQuestion(questionId, rating);
      setResults((prev) => ({ ...prev, [questionId]: result }));
      setLastResult({ ...result, prompt: question.prompt });
      setFlying({ question, result });
      setQueue((prev) => prev.filter((q) => q.id !== questionId));
      window.setTimeout(() => setFlying(null), 460);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onDeleteQuestion = async (questionId: number) => {
    if (!window.confirm("确定删除这道练习题吗？（含作答记录）")) return;
    try {
      await deleteQuestion(questionId);
      setQueue((prev) => prev.filter((q) => q.id !== questionId));
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const toggleStar = (id: number) => {
    setStarred((prev) => {
      const next = prev.includes(id)
        ? prev.filter((item) => item !== id)
        : [...prev, id];
      try {
        localStorage.setItem(STAR_KEY, JSON.stringify(next));
      } catch {
        /* 隐私模式等场景下忽略 */
      }
      return next;
    });
  };

  const tasks = queue;
  const doneCount = Object.keys(results).length;
  const answeredTotal = doneCount + queue.length;
  const selectableMistakes = mistakes.filter((item) => item.library);

  return (
    <div className="space-y-4">
      {error && <Notice kind="error">{error}</Notice>}
      {genMsg && <Notice kind="ok">{genMsg}</Notice>}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* 出题面板：竖栏（可折叠）⇄ 展开 */}
        <div className="flex shrink-0 flex-row items-center gap-2.5 self-start rounded-2xl border border-black/[0.06] bg-zinc-50 p-2 lg:w-[52px] lg:flex-col lg:py-3">
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            title="出题"
            aria-label="出题"
            className={`grid h-10 w-10 place-items-center rounded-xl transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
              panelOpen
                ? "bg-black/[0.06] text-zinc-700"
                : "bg-teal-600 text-white shadow-sm hover:bg-teal-700"
            }`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            title="学科掌握度"
            aria-label="学科掌握度"
            className="grid h-10 w-10 place-items-center rounded-xl text-zinc-500 transition hover:bg-black/[0.06] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
              <path d="M3 3v18h18" />
              <path d="m7 14 4-4 3 3 5-6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => setPanelOpen((v) => !v)}
            title={panelOpen ? "收起侧栏" : "展开侧栏"}
            aria-label={panelOpen ? "收起侧栏" : "展开侧栏"}
            className="hidden h-10 w-10 place-items-center rounded-xl text-zinc-400 transition hover:bg-black/[0.06] hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none lg:grid lg:mt-auto"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              className={`transition-transform ${panelOpen ? "rotate-180" : ""}`}
            >
              <path d="m9 18 6-6-6-6" />
            </svg>
          </button>
        </div>

        {panelOpen && (
          <div className="w-full shrink-0 space-y-2.5 lg:w-[266px]">
            <Card title="生成练习题">
              <div className="flex items-center gap-1.5">
                {(
                  [
                    { key: "mistakes" as const, label: "基于错题" },
                    { key: "knowledge_base" as const, label: "基于知识库" },
                  ]
                ).map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setSource(item.key)}
                    className={`rounded-full px-3 py-1.5 text-[11px] transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                      source === item.key
                        ? "bg-teal-600/10 font-medium text-teal-800 ring-1 ring-teal-600/40"
                        : "text-zinc-500 hover:bg-black/[0.04]"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {source === "mistakes" ? (
                <div className="mt-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[11px] text-zinc-400">
                      选择要强化的错题
                    </span>
                    <span className="text-[11px] text-teal-700">
                      已选 {pickedMistakes.length}
                    </span>
                  </div>
                  <div className="mt-1.5 max-h-56 space-y-1 overflow-y-auto pr-0.5">
                    {selectableMistakes.length === 0 && (
                      <p className="rounded-xl bg-black/[0.03] px-3 py-3 text-[11px] text-zinc-400">
                        还没有错题记录，先去「错题本」记一条
                      </p>
                    )}
                    {selectableMistakes.map((item) => {
                      const picked = pickedMistakes.includes(item.id);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() =>
                            setPickedMistakes((prev) =>
                              prev.includes(item.id)
                                ? prev.filter((id) => id !== item.id)
                                : [...prev, item.id],
                            )
                          }
                          className={`flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                            picked
                              ? "bg-teal-600/[0.08] ring-1 ring-teal-600/40"
                              : "bg-white ring-1 ring-black/[0.06] hover:bg-black/[0.03]"
                          }`}
                        >
                          <span
                            className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border transition ${
                              picked
                                ? "border-teal-600 bg-teal-600 text-white"
                                : "border-black/20"
                            }`}
                            aria-hidden
                          >
                            {picked && (
                              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20 6 9 17l-5-5" />
                              </svg>
                            )}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-[12px] text-zinc-800">
                              {item.question || item.note}
                            </span>
                            <span className="mt-0.5 block text-[10px] text-zinc-400">
                              {item.library}
                              {item.kind && KIND_LABELS[item.kind]
                                ? ` · ${KIND_LABELS[item.kind]}`
                                : ""}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  {pickedMistakes.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setPickedMistakes([])}
                      className="mt-1.5 text-[11px] text-zinc-400 transition hover:text-zinc-600"
                    >
                      清空选择
                    </button>
                  )}
                </div>
              ) : (
                <label className="mt-3 block text-[11px] text-zinc-400">
                  知识库
                  <select
                    value={library}
                    onChange={(event) => setLibrary(event.target.value)}
                    className={`mt-1.5 block w-full ${selectClass}`}
                  >
                    {libraries.map((item) => (
                      <option key={item.name} value={item.name}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div className="mt-3">
                <span className="text-[11px] text-zinc-400">难度</span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(
                    [
                      { value: "auto" as const, label: "自动" },
                      { value: "basic" as const, label: "基础" },
                      { value: "apply" as const, label: "进阶" },
                      { value: "transfer" as const, label: "迁移" },
                    ]
                  ).map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setDifficulty(option.value)}
                      className={`rounded-lg px-2.5 py-1.5 text-[11px] transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                        difficulty === option.value
                          ? "bg-teal-600/10 font-medium text-teal-800 ring-1 ring-teal-600/40"
                          : "text-zinc-500 ring-1 ring-black/[0.08] hover:bg-black/[0.04]"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-3 flex items-center gap-2.5">
                <div className="flex items-center rounded-full bg-black/[0.04] p-1">
                  <button
                    type="button"
                    onClick={() => setCount((v) => Math.max(1, v - 1))}
                    disabled={count <= 1}
                    aria-label="减少数量"
                    className="grid h-7 w-7 place-items-center rounded-full text-zinc-600 transition hover:bg-white focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-30"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                      <path d="M5 12h14" />
                    </svg>
                  </button>
                  <span className="w-7 text-center text-sm font-semibold tabular-nums">
                    {count}
                  </span>
                  <button
                    type="button"
                    onClick={() => setCount((v) => Math.min(10, v + 1))}
                    disabled={count >= 10}
                    aria-label="增加数量"
                    className="grid h-7 w-7 place-items-center rounded-full text-zinc-600 transition hover:bg-white focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-30"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => void onGenerate()}
                  disabled={busy}
                  className="flex-1 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-40"
                >
                  {busy
                    ? genProgress
                      ? `正在出第 ${genProgress.done}/${genProgress.total} 题…`
                      : "正在选题…"
                    : "生成变式题"}
                </button>
              </div>

              {/* 出题动画：骨架卡依次点亮（循环到出题完成） */}
              {busy && (
                <div className="animate-fade-up mt-3 rounded-xl bg-zinc-50 p-3.5 ring-1 ring-black/[0.05]">
                  <div className="flex items-center gap-2 text-xs font-medium text-zinc-600">
                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-teal-600/30 border-t-teal-600" />
                    {genProgress
                      ? `正在出第 ${genProgress.done}/${genProgress.total} 题…`
                      : "正在拟题…"}
                  </div>
                  <div className="mt-2.5 space-y-1.5">
                    {Array.from({ length: Math.min(count, 4) }).map((_, index) => (
                      <div
                        key={index}
                        className="qgen-card rounded-lg border border-black/[0.06] bg-white px-3 py-2"
                        style={{ animationDelay: `${index * 0.7}s` }}
                        aria-hidden
                      >
                        <div className="h-1.5 w-3/5 rounded-full bg-black/[0.08]" />
                        <div className="mt-1.5 h-1.5 w-4/5 rounded-full bg-black/[0.05]" />
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] text-zinc-400">
                    {genProgress
                      ? `${genProgress.done} / ${genProgress.total} · ${genProgress.library}`
                      : "题目会加入今日待复习"}
                  </p>
                </div>
              )}
            </Card>

            <Card title="学科掌握度">
              {weak.length === 0 ? (
                <p className="py-2 text-center text-xs text-zinc-400">
                  完成练习后自动生成掌握度分析
                </p>
              ) : (
                <ul className="space-y-3">
                  {weak.map((item) => (
                    <li key={item.library}>
                      <div className="mb-1 flex justify-between text-[11px] font-medium text-zinc-500">
                        <span>{item.library}</span>
                        <span className="tabular-nums">{item.mastery}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-black/[0.06]">
                        <div
                          className="h-full rounded-full bg-teal-600 transition-all"
                          style={{ width: `${Math.min(100, item.mastery)}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}

        {/* 牌堆复习 */}
        <div ref={reviewRef} className="min-w-0 flex-1 lg:sticky lg:top-0">
          <section className="flex flex-col overflow-hidden rounded-2xl bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] lg:max-h-[calc(100dvh-150px)]">
            <header className="border-b border-black/[0.06] p-5 pb-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold">
                  今日待复习（{queue.length}）
                </h2>
                <span className="text-[11px] tabular-nums text-zinc-500">
                  已完成 {doneCount} / 共 {answeredTotal}
                </span>
              </div>
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-black/[0.06]">
                <div
                  className="h-full rounded-full bg-teal-600 transition-all duration-500 ease-out"
                  style={{
                    width: `${answeredTotal > 0 ? (doneCount / answeredTotal) * 100 : 0}%`,
                  }}
                />
              </div>
            </header>

            <div className="flex-1 overflow-y-auto p-5">
              {tasks.length === 0 && !flying ? (
                <div className="rounded-xl border border-dashed border-black/[0.12] py-8 text-center">
                  <p className="text-xs text-zinc-500">暂无到期题目</p>
                  <p className="mt-1 text-xs text-zinc-400">
                    在左侧挑几条错题，生成变式题开始练
                  </p>
                </div>
              ) : (
                <div className="relative">
                  {flying && (
                    <div className="animate-card-fly-out pointer-events-none absolute inset-x-0 top-0 z-20 rounded-2xl border border-black/[0.06] bg-white p-4">
                      <QuestionBody question={flying.question} />
                      <p className="mt-3 text-xs font-medium text-teal-700">
                        已记录自评：掌握度 {flying.result.mastery}% ·{" "}
                        {flying.result.due_in_days > 0
                          ? `${flying.result.due_in_days} 天后再来`
                          : "稍后再来"}
                      </p>
                    </div>
                  )}

                  {tasks.slice(1, 3).map((_, index) => (
                    <div
                      key={tasks[index + 1].id}
                      aria-hidden
                      className={`absolute inset-x-3 rounded-2xl border border-black/[0.06] bg-zinc-50 ${
                        index === 0 ? "top-2 z-0" : "top-4"
                      }`}
                      style={{ height: "calc(100% - 10px)" }}
                    />
                  ))}

                  {tasks[0] && (
                    <div className="animate-fade-up relative z-10 rounded-2xl border border-black/[0.06] bg-white p-5 shadow-[0_2px_10px_rgba(0,0,0,0.05)] sm:p-6">
                      <div className="flex items-start gap-3">
                        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] bg-teal-600/10 text-sm font-semibold text-teal-800 tabular-nums">
                          {doneCount + 1}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs text-zinc-500">
                            第 {doneCount + 1} 题 · 共 {doneCount + tasks.length} 题
                          </div>
                          <div className="mt-1.5">
                            <QuestionBody question={tasks[0]} />
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-0.5">
                          <button
                            type="button"
                            onClick={() => toggleStar(tasks[0].id)}
                            aria-label={starred.includes(tasks[0].id) ? "取消星标" : "星标本题"}
                            title="星标本题"
                            className={`grid h-7 w-7 place-items-center rounded-lg transition hover:bg-black/[0.05] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                              starred.includes(tasks[0].id)
                                ? "text-amber-400"
                                : "text-zinc-300"
                            }`}
                          >
                            <svg
                              width="15"
                              height="15"
                              viewBox="0 0 24 24"
                              fill={starred.includes(tasks[0].id) ? "currentColor" : "none"}
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              aria-hidden
                            >
                              <path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2Z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => void onDeleteQuestion(tasks[0].id)}
                            aria-label="删除本题"
                            title="删除本题"
                            className="grid h-7 w-7 place-items-center rounded-lg text-zinc-300 transition hover:bg-red-50 hover:text-red-600 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <path d="M3 6h18" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      <div className="mt-4">
                        <textarea
                          rows={6}
                          maxLength={500}
                          value={drafts[tasks[0].id] ?? ""}
                          onChange={(event) =>
                            setDrafts((prev) => ({
                              ...prev,
                              [tasks[0].id]: event.target.value,
                            }))
                          }
                          placeholder="把你的思路完整写下来——写完再自评，记忆效果更好…"
                          className="w-full resize-none rounded-[14px] bg-zinc-50 px-4 py-3.5 text-sm leading-[1.8] ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
                        />
                        <div className="mt-1 flex items-center justify-between">
                          <span className="text-[10px] text-zinc-400">
                            自评参考，不会提交
                          </span>
                          <span className="text-[10px] tabular-nums text-zinc-400">
                            {(drafts[tasks[0].id] ?? "").length}/500
                          </span>
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-4 gap-2">
                        {RATINGS.map((rating) => (
                          <button
                            key={rating.value}
                            type="button"
                            onClick={() => void onAnswer(tasks[0].id, rating.value)}
                            className={`rounded-full border py-2.5 text-center text-xs font-medium transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none active:scale-95 ${rating.cls}`}
                          >
                            {rating.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {tasks.length > 1 && (
                    <p className="mt-3 text-center text-xs text-zinc-400">
                      还有 {tasks.length - 1} 题在队列里
                    </p>
                  )}

                  {lastResult && (
                    <div className="mt-3 flex items-center gap-2 px-1">
                      <svg
                        width="13"
                        height="13"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#0f766e"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                        className="shrink-0"
                      >
                        <path d="M20 6 9 17l-5-5" />
                      </svg>
                      <span className="shrink-0 text-xs text-zinc-600">
                        上一题已记录：掌握度 {lastResult.mastery}% ·{" "}
                        {lastResult.due_in_days > 0
                          ? `${lastResult.due_in_days} 天后再次复习`
                          : "稍后再来"}
                      </span>
                      {lastResult.prompt && (
                        <span className="min-w-0 flex-1 truncate text-xs text-zinc-300">
                          {lastResult.prompt}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
