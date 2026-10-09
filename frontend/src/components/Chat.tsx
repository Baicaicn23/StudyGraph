"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import {
  addFeedback,
  addNote,
  generatePractice,
  getHealth,
  listFeedback,
  listLibraries,
  resumeChat,
  streamChat,
  studyPlan,
  type Library,
  type StudyPlan,
  type StreamEvent,
} from "@/lib/api";
import Markdown from "./Markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface PendingInterrupt {
  library: string;
  title: string;
  preview: string;
}

/* 首屏快捷功能 + 快捷问题 + 底部快捷指令 */
const LEARN_FUNCTIONS = [
  "根据我的知识库出 3 道今日复习题",
  "总结我最近记录的错题",
  "帮我记一笔笔记：",
  "帮我制定今天的学习计划",
];

const SUGGESTIONS = [
  "我的薄弱学科有哪些？",
  "怎么用间隔重复复习？",
  "我的笔记里怎么讲导数的？",
  "记住：我在准备月底的微积分测验",
];

const QUICK_COMMANDS = [
  "帮我生成 3 道复习题",
  "帮我总结知识点",
  "帮我分析我的错题",
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);
  const [provider, setProvider] = useState("");
  const [pending, setPending] = useState<PendingInterrupt | null>(null);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  // 每条 AI 回复的学习操作
  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const [actionFeedback, setActionFeedback] = useState<Record<number, string>>({});
  const [kbPickerFor, setKbPickerFor] = useState<number | null>(null);
  const [kbTarget, setKbTarget] = useState("");
  const [expandedMsg, setExpandedMsg] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const threadIdRef = useRef("");
  const getThreadId = useCallback(() => {
    if (!threadIdRef.current) {
      threadIdRef.current = `web-${Math.random().toString(36).slice(2, 10)}`;
    }
    return threadIdRef.current;
  }, []);

  const refreshLibraries = useCallback(async () => {
    try {
      setLibraries(await listLibraries());
    } catch {
      // 后端未启动时保持空列表。
    }
  }, []);

  const refreshPlan = useCallback(async () => {
    try {
      setPlan(await studyPlan());
    } catch {
      // 后端未启动时忽略。
    }
  }, []);

  useEffect(() => {
     
    void refreshLibraries();
     
    void refreshPlan();
    getHealth()
      .then((h) => setProvider(h.provider))
      .catch(() => setProvider(""));
  }, [refreshLibraries, refreshPlan]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const nearBottom =
      node.scrollHeight - node.scrollTop - node.clientHeight < 200;
    if (nearBottom) {
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const onScrollChange = () => {
    const node = scrollRef.current;
    if (!node) return;
    setShowScrollBtn(
      node.scrollHeight - node.scrollTop - node.clientHeight > 300,
    );
  };

  const appendToAssistant = useCallback((delta: string) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant") {
        next[next.length - 1] = { ...last, content: last.content + delta };
      }
      return next;
    });
  }, []);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      if (event.type === "token") appendToAssistant(event.content);
      else if (event.type === "interrupt")
        setPending({
          library: event.library,
          title: event.title,
          preview: event.preview,
        });
      else if (event.type === "guard")
        appendToAssistant(`\n\n> 🚧 护栏提示：${event.reason}`);
      else if (event.type === "error")
        appendToAssistant(`\n\n> ⚠️ ${event.message}`);
    },
    [appendToAssistant],
  );

  const send = useCallback(
    async (raw?: string) => {
      const text = (raw ?? input).trim();
      if (!text || busy) return;
      setInput("");
      setPickerOpen(false);
      setPlusMenuOpen(false);
      if (inputRef.current) inputRef.current.style.height = "auto";
      setBusy(true);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ]);
      await streamChat(
        { message: text, thread_id: getThreadId(), knowledge_bases: selected },
        handleEvent,
      );
      await refreshLibraries();
      await refreshPlan();
      setBusy(false);
    },
    [
      input,
      busy,
      getThreadId,
      selected,
      handleEvent,
      refreshLibraries,
      refreshPlan,
    ],
  );

  const resolvePending = useCallback(
    async (approved: boolean) => {
      setPending(null);
      setBusy(true);
      await resumeChat(getThreadId(), approved, handleEvent);
      await refreshLibraries();
      setBusy(false);
    },
    [getThreadId, handleEvent, refreshLibraries],
  );

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  };

  const toggleLibrary = (name: string) =>
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );

  const fillInput = (text: string) => {
    setInput(text);
    setPlusMenuOpen(false);
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(
        inputRef.current.scrollHeight,
        144,
      )}px`;
      inputRef.current.focus();
    }
  };

  /* ---------- 消息学习操作 ---------- */
  const userTextBefore = (index: number): string => {
    for (let i = index - 1; i >= 0; i -= 1) {
      if (messages[i].role === "user") return messages[i].content;
    }
    return "";
  };

  const targetLibrary = () => selected[0] || libraries[0]?.name || "日常沉淀";

  const runMessageAction = async (
    index: number,
    action: "kb" | "practice" | "mistake",
  ) => {
    const msg = messages[index];
    if (!msg || actionBusy !== null) return;
    setActionBusy(index);
    try {
      if (action === "kb") {
        const lib = kbTarget || targetLibrary();
        await addNote(lib, msg.content.slice(0, 30), msg.content);
        setActionFeedback((prev) => ({
          ...prev,
          [index]: `已加入「${lib}」知识库`,
        }));
      } else if (action === "practice") {
        const lib = selected[0] || libraries[0]?.name || "";
        await generatePractice("knowledge_base", lib, 3);
        setActionFeedback((prev) => ({
          ...prev,
          [index]: "已生成 3 道练习题，到「练习复习」页作答",
        }));
        await refreshPlan();
      } else {
        await addFeedback(
          targetLibrary(),
          userTextBefore(index),
          msg.content.slice(0, 2000),
        );
        setActionFeedback((prev) => ({ ...prev, [index]: "已标记为误区" }));
        await refreshPlan();
      }
    } catch (err) {
      setActionFeedback((prev) => ({
        ...prev,
        [index]: `操作失败：${(err as Error).message}`,
      }));
    } finally {
      setActionBusy(null);
    }
  };

  /* ---------- 引用最新错题 ---------- */
  const quoteLatestMistake = async () => {
    try {
      const feedback = await listFeedback();
      if (feedback.length === 0) {
        fillInput("我还没有记录错题。");
        return;
      }
      const latest = feedback[0];
      fillInput(
        `关于我的错题「${latest.question || latest.note}」，帮我分析一下`,
      );
    } catch {
      fillInput("帮我分析我的错题");
    }
  };

  const modelLabel = provider === "mock" ? "Mock 模型" : provider;
  const totalDocs = libraries.reduce(
    (sum, item) => sum + item.document_count,
    0,
  );

  return (
    <div className="relative flex h-full flex-col bg-white">
      {/* 顶部：标题 */}
      <header className="px-6 pt-6 pb-2">
        <h1 className="text-[17px] font-bold tracking-tight">聊天</h1>
        {selected.length > 0 && (
          <p className="mt-0.5 text-xs text-teal-700">
            检索限定：{selected.join("、")}
          </p>
        )}
      </header>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        onScroll={onScrollChange}
        className="flex-1 overflow-y-auto px-6 pb-40"
      >
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 ? (
            /* ---------- 学习型欢迎首屏 ---------- */
            <div className="mt-10 text-center">
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-teal-700 text-lg font-bold text-white shadow-lg">
                SG
              </div>
              <h2 className="text-2xl font-bold tracking-tight">
                你好，我是 StudyGraph
              </h2>
              <p className="mt-2 text-sm text-zinc-500">
                把资料沉淀进学科库，期末从库里长出复习材料。
              </p>

              {/* 轻量学习数据概览 */}
              <div className="mx-auto mt-7 grid max-w-lg grid-cols-3 gap-3">
                {[
                  {
                    label: "今日待复习",
                    value: plan ? plan.due_questions.length : "—",
                    href: "/plan",
                  },
                  {
                    label: "近 7 天误区",
                    value: plan ? plan.recent_mistakes : "—",
                    href: "/mistakes",
                  },
                  {
                    label: "知识库条目",
                    value: libraries.length > 0 ? totalDocs : "—",
                    href: "/knowledge",
                  },
                ].map((stat) => (
                  <Link
                    key={stat.label}
                    href={stat.href}
                    className="rounded-xl bg-black/[0.03] px-3 py-3.5 transition hover:bg-teal-600/[0.07] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    <div className="text-2xl font-bold tracking-tight text-teal-700 tabular-nums">
                      {stat.value}
                    </div>
                    <div className="mt-0.5 text-[11px] text-zinc-500">
                      {stat.label}
                    </div>
                  </Link>
                ))}
              </div>

              {/* 快捷功能区 */}
              <div className="mx-auto mt-6 flex max-w-xl flex-wrap justify-center gap-2">
                {LEARN_FUNCTIONS.map((text) => (
                  <button
                    key={text}
                    type="button"
                    onClick={() => fillInput(text)}
                    disabled={busy}
                    className="rounded-full bg-black/[0.04] px-3.5 py-2 text-xs font-medium text-zinc-700 transition hover:bg-teal-600/10 hover:text-teal-800 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-50"
                  >
                    {text}
                  </button>
                ))}
              </div>

              {/* 快捷问题 */}
              <div className="mx-auto mt-6 grid max-w-xl gap-2 text-left">
                {SUGGESTIONS.map((text) => (
                  <button
                    key={text}
                    type="button"
                    onClick={() => void send(text)}
                    disabled={busy}
                    className="group flex items-center gap-3 rounded-xl bg-black/[0.03] px-4 py-3 text-left text-sm transition hover:bg-black/[0.06] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="flex-1 text-zinc-700">{text}</span>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden
                      className="shrink-0 text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-teal-600"
                    >
                      <path d="M5 12h14" />
                      <path d="m12 5 7 7-7 7" />
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-5 pt-2">
              {messages.map((message, index) => (
                <div key={index} className="animate-fade-up">
                  <MessageRow
                    message={message}
                    busy={busy}
                    index={index}
                    actionBusy={actionBusy === index}
                    feedback={actionFeedback[index]}
                    libraries={libraries}
                    kbTarget={kbTarget}
                    onKbTargetChange={setKbTarget}
                    kbPickerFor={kbPickerFor}
                    onToggleKbPicker={() =>
                      setKbPickerFor((v) => (v === index ? null : index))
                    }
                    expanded={expandedMsg === index}
                    onToggleExpand={() =>
                      setExpandedMsg((v) => (v === index ? null : index))
                    }
                    onAction={(action) => void runMessageAction(index, action)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 返回最新 */}
      {showScrollBtn && (
        <button
          type="button"
          onClick={() =>
            scrollRef.current?.scrollTo({
              top: scrollRef.current.scrollHeight,
              behavior: "smooth",
            })
          }
          aria-label="返回最新消息"
          className="absolute bottom-36 right-8 z-20 grid h-9 w-9 place-items-center rounded-full bg-white text-zinc-600 shadow-lg ring-1 ring-black/10 transition hover:text-teal-700"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M12 5v14" />
            <path d="m19 12-7 7-7-7" />
          </svg>
        </button>
      )}

      {/* 底部输入区 */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-white via-white/90 to-transparent px-6 pb-4 pt-10">
        <div className="pointer-events-auto relative mx-auto max-w-3xl">
          {/* 快捷指令条 */}
          {messages.length > 0 && !input && (
            <div className="animate-fade-up mb-2 flex flex-wrap gap-1.5">
              {QUICK_COMMANDS.map((cmd) => (
                <button
                  key={cmd}
                  type="button"
                  onClick={() => fillInput(cmd)}
                  className="rounded-full bg-black/[0.04] px-3 py-1 text-[11px] text-zinc-500 transition hover:bg-teal-600/10 hover:text-teal-800 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                >
                  {cmd}
                </button>
              ))}
            </div>
          )}

          {/* + 功能菜单 */}
          {plusMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setPlusMenuOpen(false)}
                aria-hidden
              />
              <div className="animate-pop-in absolute bottom-full left-0 z-50 mb-2 w-56 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
                <Link
                  href="/knowledge"
                  onClick={() => setPlusMenuOpen(false)}
                  className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                    <path d="M12 18v-6M9 15l3 3 3-3" />
                  </svg>
                  上传资料到知识库
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setPlusMenuOpen(false);
                    void quoteLatestMistake();
                  }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v4l2.5 2.5" />
                  </svg>
                  引用最新错题
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPlusMenuOpen(false);
                    setPickerOpen(true);
                  }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
                  </svg>
                  选择检索学科
                </button>
              </div>
            </>
          )}

          {/* 学科范围选择弹层 */}
          {pickerOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setPickerOpen(false)}
                aria-hidden
              />
              <div className="animate-pop-in absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
                <div className="px-2.5 py-1.5 text-[11px] font-medium text-zinc-400">
                  检索范围（可多选）
                </div>
                {libraries.map((library) => {
                  const checked = selected.includes(library.name);
                  return (
                    <button
                      key={library.name}
                      type="button"
                      onClick={() => toggleLibrary(library.name)}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                    >
                      <span
                        className={`grid h-4 w-4 shrink-0 place-items-center rounded border transition ${
                          checked
                            ? "border-teal-600 bg-teal-600 text-white"
                            : "border-black/20"
                        }`}
                      >
                        {checked && (
                          <svg
                            width="10"
                            height="10"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden
                          >
                            <path d="m5 13 4 4L19 7" />
                          </svg>
                        )}
                      </span>
                      <span className="flex-1 truncate">{library.name}</span>
                      <span className="text-[11px] tabular-nums text-zinc-400">
                        {library.document_count}
                      </span>
                    </button>
                  );
                })}
                {selected.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelected([])}
                    className="mt-1 w-full rounded-lg px-2.5 py-1.5 text-center text-xs text-teal-700 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    清空选择（检索全部学科库）
                  </button>
                )}
              </div>
            </>
          )}

          {/* 输入栏 */}
          <div className="flex items-end gap-1.5 rounded-2xl bg-white p-2 shadow-lg shadow-black/[0.06] ring-1 ring-black/10 transition focus-within:ring-2 focus-within:ring-teal-600">
            <button
              type="button"
              onClick={() => setPlusMenuOpen((v) => !v)}
              aria-expanded={plusMenuOpen}
              aria-label="更多功能"
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none ${
                plusMenuOpen
                  ? "bg-black/[0.06] text-zinc-900"
                  : "text-zinc-500 hover:bg-black/[0.06]"
              }`}
            >
              <svg
                width="17"
                height="17"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(event) => {
                setInput(event.target.value);
                const el = event.target;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
              }}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="输入你的问题，或描述你要生成的复习材料…"
              className="max-h-36 min-w-0 flex-1 resize-none self-center bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-zinc-400"
            />
            <button
              type="button"
              onClick={() => setPickerOpen((v) => !v)}
              className="hidden shrink-0 self-center rounded-full px-2.5 py-1 text-[11px] font-medium text-zinc-400 transition hover:text-zinc-600 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none sm:block"
            >
              {selected.length > 0
                ? `已选 ${selected.length} 个学科库`
                : "全部学科库"}
            </button>
            {modelLabel && (
              <span className="hidden shrink-0 self-center items-center gap-1 rounded-full border border-black/[0.08] px-2.5 py-1 text-[11px] font-medium text-zinc-500 md:inline-flex">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    provider === "mock" ? "bg-zinc-300" : "bg-teal-600"
                  }`}
                />
                {modelLabel}
              </span>
            )}
            <button
              type="button"
              onClick={() => void send()}
              disabled={busy || !input.trim()}
              aria-label="发送"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-95 disabled:opacity-25"
            >
              {busy ? (
                <span className="block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M12 19V5" />
                  <path d="m5 12 7-7 7 7" />
                </svg>
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-zinc-400">
            内容由AI生成，请核实重要信息 · Enter 发送 · Shift+Enter 换行
          </p>
        </div>
      </div>

      {/* HITL 确认框 */}
      {pending && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 backdrop-blur-sm">
          <div className="animate-pop-in w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="text-lg font-bold tracking-tight">需要你的确认</h2>
            <p className="mt-1 text-sm text-zinc-500">
              助手想把一条笔记保存到你的知识库：
            </p>
            <div className="mt-4 rounded-xl bg-black/[0.04] p-4 text-sm">
              <div className="font-semibold">
                「{pending.library}」 · {pending.title}
              </div>
              <p className="mt-1.5 line-clamp-4 text-zinc-500">
                {pending.preview}
              </p>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => void resolvePending(false)}
                className="rounded-full bg-black/[0.06] px-5 py-2 text-sm font-medium text-zinc-700 transition hover:bg-black/[0.1] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void resolvePending(true)}
                className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                确认保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageRow({
  message,
  busy,
  index,
  actionBusy,
  feedback,
  libraries,
  kbTarget,
  onKbTargetChange,
  kbPickerFor,
  onToggleKbPicker,
  expanded,
  onToggleExpand,
  onAction,
}: {
  message: Message;
  busy: boolean;
  index: number;
  actionBusy: boolean;
  feedback?: string;
  libraries: Library[];
  kbTarget: string;
  onKbTargetChange: (value: string) => void;
  kbPickerFor: number | null;
  onToggleKbPicker: () => void;
  expanded: boolean;
  onToggleExpand: () => void;
  onAction: (action: "kb" | "practice" | "mistake") => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-teal-600 px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const isLong = message.content.length > 1500;
  const shown =
    isLong && !expanded ? `${message.content.slice(0, 1500)}…` : message.content;

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-teal-700 text-[9px] font-bold text-white">
        SG
      </div>
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-lg bg-white px-4 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] ring-1 ring-black/[0.04]">
          {message.content ? (
            <div className="prose prose-zinc max-w-none text-sm">
              <Markdown content={shown} />
            </div>
          ) : busy ? (
            <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-zinc-300" />
          ) : null}
          {isLong && (
            <button
              type="button"
              onClick={onToggleExpand}
              className="mt-1 text-xs font-medium text-teal-700 underline-offset-2 hover:underline"
            >
              {expanded ? "收起" : "展开全文"}
            </button>
          )}
        </div>

        {/* 学习专属操作栏 */}
        {message.content && !busy && (
          <div className="mt-1.5 flex items-center gap-3 px-1">
            <button
              type="button"
              onClick={onToggleKbPicker}
              disabled={actionBusy}
              className="text-[11px] font-medium text-zinc-400 transition hover:text-teal-700 disabled:opacity-40"
            >
              加入知识库
            </button>
            <button
              type="button"
              onClick={() => onAction("practice")}
              disabled={actionBusy}
              className="text-[11px] font-medium text-zinc-400 transition hover:text-teal-700 disabled:opacity-40"
            >
              {actionBusy ? "处理中…" : "生成练习题"}
            </button>
            <button
              type="button"
              onClick={() => onAction("mistake")}
              disabled={actionBusy}
              className="text-[11px] font-medium text-zinc-400 transition hover:text-teal-700 disabled:opacity-40"
            >
              标记为误区
            </button>
            {feedback && (
              <span className="animate-fade-up text-[11px] text-teal-700">
                {feedback}
              </span>
            )}
          </div>
        )}

        {/* 加入知识库：选库确认 */}
        {kbPickerFor === index && (
          <div className="animate-fade-up mt-2 flex items-center gap-2 rounded-xl bg-black/[0.03] p-2.5">
            <select
              value={kbTarget}
              onChange={(event) => onKbTargetChange(event.target.value)}
              className="rounded-lg bg-white px-2 py-1.5 text-xs ring-1 ring-black/10 outline-none transition focus:ring-2 focus:ring-teal-600"
            >
              {(libraries.length > 0
                ? libraries.map((item) => item.name)
                : ["日常沉淀"]
              ).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => onAction("kb")}
              disabled={actionBusy}
              className="rounded-full bg-teal-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
            >
              {actionBusy ? "保存中…" : "确认加入"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
