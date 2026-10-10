"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  answerQuestion,
  deleteQuestion,
  dueQuestions,
  generatePracticeStream,
  listLibraries,
  studyPlan,
  type AnswerResult,
  type GenerateProgress,
  type Library,
  type PracticeDifficulty,
  type PracticeRating,
  type PracticeSource,
  type Question,
  type WeakLibrary,
} from "@/lib/api";
import {
  Card,
  Notice,
  Page,
  selectClass,
} from "@/components/ui";

const RATINGS: { value: PracticeRating; label: string; cls: string }[] = [
  {
    value: "again",
    label: "又忘了",
    cls: "border-red-200 text-red-600 hover:bg-red-50 active:border-red-600 active:bg-red-600 active:text-white",
  },
  {
    value: "hard",
    label: "有点难",
    cls: "border-zinc-300 text-zinc-600 hover:bg-zinc-50 active:border-zinc-700 active:bg-zinc-700 active:text-white",
  },
  {
    value: "good",
    label: "掌握了",
    cls: "border-emerald-200 text-emerald-600 hover:bg-emerald-50 active:border-emerald-600 active:bg-emerald-600 active:text-white",
  },
  {
    value: "easy",
    label: "太简单",
    cls: "border-emerald-500 text-emerald-700 hover:bg-emerald-50 active:border-emerald-700 active:bg-emerald-700 active:text-white",
  },
];

const STAR_KEY = "studygraph-starred-questions";
const MISTAKE_MARKER = "【你当时记下的误区】";

/** 难度档位的展示标签与配色（数据色 teal 主导，迁移档用暖色点缀区分）。 */
const DIFFICULTY_TAGS: Record<string, { label: string; cls: string }> = {
  basic: { label: "基础", cls: "bg-black/[0.05] text-zinc-600" },
  apply: { label: "进阶", cls: "bg-teal-600/10 text-teal-700" },
  transfer: { label: "迁移", cls: "bg-amber-500/10 text-amber-700" },
};

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
      <p className="mt-2.5 whitespace-pre-wrap text-sm leading-relaxed text-zinc-800">
        {main}
      </p>
      {note && (
        <div className="mt-2.5 rounded-lg bg-red-50/70 p-3">
          <p className="text-xs font-semibold text-red-600">
            你当时记下的误区
          </p>
          <p className="mt-1 text-sm leading-relaxed text-red-900/80">
            {note}
          </p>
        </div>
      )}
    </>
  );
}

export default function PracticePage() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [source, setSource] = useState<PracticeSource>("knowledge_base");
  const [library, setLibrary] = useState("");
  const [count, setCount] = useState(3);
  const [difficulty, setDifficulty] = useState<PracticeDifficulty>("auto");
  const [generated, setGenerated] = useState<Question[]>([]);
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
  const [autoStart, setAutoStart] = useState(true);
  const [starred, setStarred] = useState<number[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  // 卡片堆叠：刚作答完、正在播放「飞走」动画的牌
  const [flying, setFlying] = useState<{
    question: Question;
    result: AnswerResult;
  } | null>(null);

  const reviewRef = useRef<HTMLDivElement>(null);
  const generateRef = useRef<HTMLDivElement>(null);
  const reviewListRef = useRef<HTMLDivElement>(null);

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
    try {
      setStarred(JSON.parse(localStorage.getItem(STAR_KEY) ?? "[]") as number[]);
    } catch {
      setStarred([]);
    }
  }, [refresh]);

  const onGenerate = async () => {
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
      );
      setGenerated(questions);
      setGenMsg(`已生成 ${questions.length} 道题，已加入今日待复习`);
      await refresh();
      if (autoStart) {
        reviewRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    } catch (err) {
      setError((err as Error).message);
      setGenerated([]);
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
      // 先把这张牌标记为「飞走」，出队交给动画结束时（flying 清空即消失）
      setFlying({ question, result });
      setQueue((prev) => prev.filter((q) => q.id !== questionId));
      window.setTimeout(() => setFlying(null), 460);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onDeleteQuestion = async (questionId: number) => {
    const ok = window.confirm("确定删除这道练习题吗？（含作答记录）");
    if (!ok) return;
    setError("");
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

  const answeredTotal = Object.keys(results).length + queue.length;
  const doneCount = Object.keys(results).length;

  return (
    <Page
      wide
      title="练习与复习"
      subtitle="出题 → 自评 → 掌握度与下次复习时间自动更新（间隔重复）。"
    >
      {error && <Notice kind="error">{error}</Notice>}

      {/* 左窄右宽：35% 功能控制区 / 65% 复习主区 */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,35fr)_minmax(0,65fr)]">
        {/* 左栏：出题 → 看掌握度 */}
        <div className="space-y-6">
          <div ref={generateRef}>
            <Card title="生成练习题">
              {/* 出题来源 / 知识库：横向并排 */}
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[11px] text-zinc-400">
                  出题来源
                  <select
                    value={source}
                    onChange={(event) =>
                      setSource(event.target.value as PracticeSource)
                    }
                    className={`mt-1.5 block w-full ${selectClass}`}
                  >
                    <option value="knowledge_base">来自知识库</option>
                    <option value="mistakes">来自我的错题</option>
                  </select>
                </label>
                {source === "knowledge_base" && (
                  <label className="block text-[11px] text-zinc-400">
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
              </div>

              {/* 难度选择：auto 按学科掌握度自动分档 */}
              <label className="mt-3 block text-[11px] text-zinc-400">
                难度
                <select
                  value={difficulty}
                  onChange={(event) =>
                    setDifficulty(event.target.value as PracticeDifficulty)
                  }
                  className={`mt-1.5 block w-full ${selectClass}`}
                >
                  <option value="auto">自动（按掌握度）</option>
                  <option value="basic">基础（记忆与理解）</option>
                  <option value="apply">进阶（情境应用）</option>
                  <option value="transfer">迁移（举一反三）</option>
                </select>
              </label>

              {/* 数量步进器 + 生成按钮 同行 */}
              <div className="mt-3 flex items-end gap-3">
                <div className="flex items-center rounded-full bg-black/[0.04] p-1">
                  <button
                    type="button"
                    onClick={() => setCount((v) => Math.max(1, v - 1))}
                    disabled={count <= 1}
                    aria-label="减少数量"
                    className="grid h-7 w-7 place-items-center rounded-full text-zinc-600 transition hover:bg-white focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-30"
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      aria-hidden
                    >
                      <path d="M5 12h14" />
                    </svg>
                  </button>
                  <span className="w-8 text-center text-sm font-semibold tabular-nums">
                    {count}
                  </span>
                  <button
                    type="button"
                    onClick={() => setCount((v) => Math.min(10, v + 1))}
                    disabled={count >= 10}
                    aria-label="增加数量"
                    className="grid h-7 w-7 place-items-center rounded-full text-zinc-600 transition hover:bg-white focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-30"
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      aria-hidden
                    >
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => void onGenerate()}
                  disabled={busy || (source === "knowledge_base" && !library)}
                  className="flex-1 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-40"
                >
                  {busy
                    ? genProgress
                      ? `正在出第 ${genProgress.done}/${genProgress.total} 题…`
                      : "正在选题…"
                    : "生成"}
                </button>
              </div>

              {/* 生成进度条：每出一题推进一格 */}
              {busy && genProgress && (
                <div className="animate-fade-up mt-3">
                  <div className="h-1.5 overflow-hidden rounded-full bg-black/[0.06]">
                    <div
                      className="h-full rounded-full bg-teal-600 transition-all duration-500 ease-out"
                      style={{
                        width: `${(genProgress.done / genProgress.total) * 100}%`,
                      }}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-zinc-400">
                    {genProgress.done} / {genProgress.total} ·{" "}
                    {genProgress.library}
                    {genProgress.difficulty && (
                      <>
                        {" · "}
                        {DIFFICULTY_TAGS[genProgress.difficulty]?.label ??
                          genProgress.difficulty}
                      </>
                    )}
                  </p>
                </div>
              )}

              {/* 自动开始复习 */}
              <label className="mt-4 flex cursor-pointer items-center gap-2 text-xs text-zinc-400">
                <input
                  type="checkbox"
                  checked={autoStart}
                  onChange={(event) => setAutoStart(event.target.checked)}
                  className="peer sr-only"
                />
                <span
                  className={`grid h-4 w-4 place-items-center rounded border transition peer-checked:border-teal-600 peer-checked:bg-teal-600 peer-checked:text-white ${
                    autoStart ? "border-teal-600 bg-teal-600 text-white" : "border-black/20"
                  }`}
                  aria-hidden
                >
                  {autoStart && (
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 6 9 17l-5-5" />
                    </svg>
                  )}
                </span>
                生成后自动开始复习
              </label>

              {genMsg && (
                <p className="animate-fade-up mt-3 rounded-xl bg-teal-50 px-3 py-2 text-xs text-teal-800 ring-1 ring-teal-600/10">
                  {genMsg}
                </p>
              )}

              {/* 生成结果预览 */}
              {generated.length > 0 && (
                <ul className="mt-4 space-y-2.5">
                  {generated.map((question) => (
                    <li
                      key={question.id}
                      className="animate-fade-up rounded-xl bg-black/[0.03] p-3.5 text-sm"
                    >
                      <div className="mb-1.5 flex items-center gap-2 text-[11px] text-zinc-500">
                        <span className="rounded-full bg-white px-2 py-0.5 font-medium">
                          {question.library}
                        </span>
                        {question.source === "mistake" && (
                          <span className="rounded-full bg-accent/10 px-2 py-0.5 font-medium text-accent">
                            来自你的误区
                          </span>
                        )}
                        <DifficultyTag difficulty={question.difficulty} />
                      </div>
                      <p className="line-clamp-3 whitespace-pre-wrap leading-relaxed text-zinc-700">
                        {question.prompt}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card title="学科掌握度">
            {weak.length === 0 ? (
              <div className="py-6 text-center">
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
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v4l2.5 2.5" />
                  </svg>
                </div>
                <p className="mt-2.5 text-sm font-medium text-zinc-600">
                  还没有掌握度数据
                  <span className="font-normal text-zinc-400">，先做几道题</span>
                </p>
                <button
                  type="button"
                  onClick={() => {
                    generateRef.current?.scrollIntoView({
                      behavior: "smooth",
                      block: "start",
                    });
                  }}
                  className="mt-1.5 block w-full text-xs font-semibold text-teal-700 underline-offset-2 hover:underline"
                >
                  去生成练习 →
                </button>
              </div>
            ) : (
              <ul className="space-y-3.5">
                {weak.map((item) => (
                  <li key={item.library}>
                    <div className="mb-1.5 flex justify-between text-xs font-medium text-zinc-500">
                      <span>{item.library}</span>
                      <span className="tabular-nums">{item.mastery}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-black/[0.06]">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-teal-400 to-teal-600 transition-all"
                        style={{ width: `${Math.min(100, item.mastery)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* 右栏：今日待复习（独立滚动） */}
        <div ref={reviewRef} className="lg:sticky lg:top-0">
          <section className="flex flex-col overflow-hidden rounded-xl bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] lg:max-h-[calc(100dvh-150px)]">
            {/* 吸顶标题栏 */}
            <header className="border-b border-black/[0.06] p-5 pb-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold">
                  今日待复习（{queue.length}）
                </h2>
                <span className="text-[11px] tabular-nums text-zinc-400">
                  已完成 {doneCount} / 共 {answeredTotal}
                </span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/[0.06]">
                <div
                  className="h-full rounded-full bg-teal-600 transition-all duration-500 ease-out"
                  style={{
                    width: `${answeredTotal > 0 ? (doneCount / answeredTotal) * 100 : 0}%`,
                  }}
                />
              </div>
            </header>

            {/* 题目列表（独立滚动） */}
            <div ref={reviewListRef} className="flex-1 space-y-6 overflow-y-auto p-5">
              {lastResult && (
                <div className="animate-fade-up flex items-start gap-2.5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-600/10">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                    className="mt-0.5 shrink-0"
                  >
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                  <div className="min-w-0">
                    <p className="font-medium tabular-nums">
                      已记录自评：掌握度 {lastResult.mastery}% ·{" "}
                      {lastResult.due_in_days > 0
                        ? `${lastResult.due_in_days} 天后再次复习`
                        : "稍后再来一题"}
                    </p>
                    {lastResult.prompt && (
                      <p className="mt-0.5 truncate text-xs text-emerald-700/80">
                        {lastResult.prompt}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {queue.length === 0 && !flying ? (
                <p className="py-10 text-center text-sm text-zinc-400">
                  暂无到期题目。去左侧生成几道吧。
                </p>
              ) : (
                <div className="relative">
                  {/* 飞走动画中的牌：盖在牌堆原位，动画结束即卸载 */}
                  {flying && (
                    <div className="animate-card-fly-out pointer-events-none absolute inset-x-0 top-0 z-20 rounded-2xl border border-black/[0.06] bg-white p-4">
                      <QuestionBody question={flying.question} />
                      <p className="mt-3 text-xs font-medium text-emerald-700">
                        已记录自评：掌握度 {flying.result.mastery}% ·{" "}
                        {flying.result.due_in_days > 0
                          ? `${flying.result.due_in_days} 天后再来`
                          : "稍后再来"}
                      </p>
                    </div>
                  )}

                  {/* 堆叠卡背：露出的下一题边缘 */}
                  {queue.slice(1, 3).map((_, index) => (
                    <div
                      key={queue[index + 1].id}
                      aria-hidden
                      className={`absolute inset-x-3 rounded-2xl border border-black/[0.06] bg-zinc-50 ${
                        index === 0 ? "top-2 z-0" : "top-4"
                      }`}
                      style={{ height: "calc(100% - 10px)" }}
                    />
                  ))}

                  {/* 当前牌 */}
                  {queue[0] && (
                    <div className="animate-fade-up relative z-10 rounded-2xl border border-black/[0.06] bg-white p-4 shadow-[0_2px_10px_rgba(0,0,0,0.05)]">
                      <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1">
                          <QuestionBody question={queue[0]} />
                        </div>
                        <div className="flex shrink-0 items-center gap-0.5">
                          <button
                            type="button"
                            onClick={() => toggleStar(queue[0].id)}
                            aria-label={starred.includes(queue[0].id) ? "取消星标" : "星标本题"}
                            title="星标本题"
                            className={`grid h-6 w-6 place-items-center rounded-lg transition hover:bg-black/[0.05] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                              starred.includes(queue[0].id)
                                ? "text-amber-400"
                                : "text-zinc-300"
                            }`}
                          >
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill={starred.includes(queue[0].id) ? "currentColor" : "none"}
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
                            onClick={() => void onDeleteQuestion(queue[0].id)}
                            aria-label="删除本题"
                            title="删除本题"
                            className="grid h-6 w-6 place-items-center rounded-lg text-zinc-300 transition hover:bg-red-50 hover:text-red-600 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <path d="M3 6h18" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      </div>

                      {/* 作答区 */}
                      <div className="relative mt-3">
                        <textarea
                          rows={3}
                          maxLength={500}
                          value={drafts[queue[0].id] ?? ""}
                          onChange={(event) =>
                            setDrafts((prev) => ({
                              ...prev,
                              [queue[0].id]: event.target.value,
                            }))
                          }
                          placeholder="写下你的作答（自评用，不会提交）…"
                          className="w-full resize-none rounded-xl bg-zinc-50 px-3.5 py-2.5 pb-6 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
                        />
                        <span className="pointer-events-none absolute bottom-2 right-3 text-[10px] tabular-nums text-zinc-300/90">
                          {(drafts[queue[0].id] ?? "").length}/500
                        </span>
                      </div>
                      <div className="mt-2.5 grid grid-cols-4 gap-2">
                        {RATINGS.map((rating) => (
                          <button
                            key={rating.value}
                            type="button"
                            onClick={() => void onAnswer(queue[0].id, rating.value)}
                            className={`rounded-full border bg-zinc-50 py-2 text-xs font-medium text-center transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none active:scale-95 ${rating.cls}`}
                          >
                            {rating.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {queue.length > 1 && (
                    <p className="mt-3 text-center text-xs text-zinc-400">
                      还有 {queue.length - 1} 题在队列里
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </Page>
  );
}
