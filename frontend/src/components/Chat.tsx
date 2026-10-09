"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import {
  addFeedback,
  addNote,
  createProject,
  generatePractice,
  getHealth,
  listChatMessages,
  listChats,
  listFeedback,
  listLibraries,
  listProjects,
  resumeChat,
  streamChat,
  studyPlan,
  type ChatProject,
  type Library,
  type StudyPlan,
  type StreamEvent,
} from "@/lib/api";
import { CHAT_ACTION_EVENT, notifyChatsChanged } from "./ChatsSection";
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

  /* ---------- 会话自动保存（全局侧栏展示，通过事件通知刷新） ---------- */
  // 当前会话（null = 还没落库，首轮回复后端会自动新建并推回 id）
  const sessionIdRef = useRef<number | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);

  /* ---------- 项目（空间）列表：输入栏下方的空间选择器用 ---------- */
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [spaceOpen, setSpaceOpen] = useState(false);
  const [spaceCreating, setSpaceCreating] = useState(false);
  const [newSpaceName, setNewSpaceName] = useState("");
  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await listProjects());
    } catch {
      /* 后端未启动 */
    }
  }, []);
  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  // 没选过空间时自动选中「默认对话空间」（后端保证一定存在）
  useEffect(() => {
    if (activeProjectId !== null || projects.length === 0) return;
    const fallback = projects.find((p) => p.is_default) ?? projects[0];
    setActiveProjectId(fallback.id);
  }, [projects, activeProjectId]);
  const activeSpace = projects.find((p) => p.id === activeProjectId);

  /** 下拉里直接新建空间：成功后自动选中它 */
  const handleCreateSpace = useCallback(async () => {
    const name = newSpaceName.trim();
    if (!name) {
      setSpaceCreating(false);
      return;
    }
    try {
      const created = await createProject(name);
      setNewSpaceName("");
      setSpaceCreating(false);
      await refreshProjects();
      setActiveProjectId(created.id);
      notifyChatsChanged(); // 让全局侧栏同步出现这个新空间
    } catch {
      /* 重名等错误静默 */
    }
  }, [newSpaceName, refreshProjects]);

  /* ---------- 平滑打字机：token 先入队列，rAF 按需吐字 ---------- */
  const queueRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const busyRef = useRef(false);
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
  const pumpRef = useRef<() => void>(() => {});
  useEffect(() => {
    pumpRef.current = () => {
      const queue = queueRef.current;
      if (queue) {
        // 自适应速度：积压越多吐得越快，积压小则逐字浮现
        const size = Math.max(2, Math.ceil(queue.length / 12));
        queueRef.current = queue.slice(size);
        appendToAssistant(queue.slice(0, size));
      }
      if (queueRef.current || busyRef.current) {
        rafRef.current = window.requestAnimationFrame(() => pumpRef.current());
      } else {
        rafRef.current = null;
      }
    };
  }, [appendToAssistant]);
  useEffect(
    () => () => {
      if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
    },
    [],
  );
  const startPump = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = window.requestAnimationFrame(() => pumpRef.current());
    }
  }, []);

  /* ---------- 状态行（理解问题 / 检索知识库…） ---------- */
  const [statusLabel, setStatusLabel] = useState("");

  /* ---------- 权限：允许完全访问（保存笔记等不再逐次确认） ---------- */
  const [fullAccess, setFullAccess] = useState(false);
  const fullAccessRef = useRef(false);
  useEffect(() => {
    // 记住用户的选择（localStorage）
    try {
      fullAccessRef.current =
        localStorage.getItem("studygraph-full-access") === "1";
      setFullAccess(fullAccessRef.current);
    } catch {
      /* ignore */
    }
  }, []);
  const toggleFullAccess = useCallback(() => {
    setFullAccess((prev) => {
      const next = !prev;
      fullAccessRef.current = next;
      try {
        localStorage.setItem("studygraph-full-access", next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
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

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      if (event.type === "token") {
        // token 进队列，由打字机节奏渲染，避免一坨糊出来
        queueRef.current += event.content;
      } else if (event.type === "status") {
        setStatusLabel(event.label);
      } else if (event.type === "session") {
        // 后端自动保存/自动起标题 → 记住会话 id，通知全局侧栏刷新
        if (sessionIdRef.current === null) {
          sessionIdRef.current = event.id;
        }
        notifyChatsChanged();
      } else if (event.type === "interrupt") {
        if (fullAccessRef.current) {
          // 允许完全访问：自动同意保存，不再弹确认框
          setStatusLabel("已自动允许保存笔记");
          resolveRef.current(true);
        } else {
          setPending({
            library: event.library,
            title: event.title,
            preview: event.preview,
          });
        }
      } else if (event.type === "guard") {
        appendToAssistant(`\n\n> 🚧 护栏提示：${event.reason}`);
      } else if (event.type === "error") {
        appendToAssistant(`\n\n> ⚠️ ${event.message}`);
      }
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
      busyRef.current = true;
      setStatusLabel("正在理解问题…");
      startPump();
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ]);
      await streamChat(
        {
          message: text,
          thread_id: getThreadId(),
          knowledge_bases: selected,
          session_id: sessionIdRef.current ?? undefined,
          project_id: activeProjectId ?? undefined,
        },
        handleEvent,
      );
      busyRef.current = false;
      setStatusLabel("");
      await refreshLibraries();
      await refreshPlan();
      setBusy(false);
    },
    [
      input,
      busy,
      getThreadId,
      selected,
      activeProjectId,
      handleEvent,
      refreshLibraries,
      refreshPlan,
      startPump,
    ],
  );

  const resolvePending = useCallback(
    async (approved: boolean) => {
      setPending(null);
      setBusy(true);
      busyRef.current = true;
      startPump();
      await resumeChat(
        getThreadId(),
        approved,
        handleEvent,
        sessionIdRef.current ?? undefined,
      );
      busyRef.current = false;
      await refreshLibraries();
      setBusy(false);
    },
    [getThreadId, handleEvent, refreshLibraries, startPump],
  );
  // handleEvent 里要在 interrupt 时自动放行，用 ref 持有最新的 resume 入口
  const resolveRef = useRef<(approved: boolean) => void>(() => {});
  useEffect(() => {
    resolveRef.current = (approved: boolean) => void resolvePending(approved);
  }, [resolvePending]);

  /* ---------- 会话切换 ---------- */
  const startNewChat = useCallback(
    (projectId?: number) => {
      if (busy) return;
      sessionIdRef.current = null;
      threadIdRef.current = "";
      setStatusLabel("");
      queueRef.current = "";
      setMessages([]);
      if (projectId !== undefined) setActiveProjectId(projectId);
    },
    [busy],
  );

  const openSession = useCallback(async (sessionId: number) => {
    if (busyRef.current) return;
    sessionIdRef.current = sessionId;
    try {
      const [history, allChats] = await Promise.all([
        listChatMessages(sessionId),
        listChats(),
      ]);
      const meta = allChats.find((chat) => chat.id === sessionId);
      threadIdRef.current = meta?.thread_id || `web-s${sessionId}`;
      setActiveProjectId(meta?.project_id ?? null);
      setStatusLabel("");
      queueRef.current = "";
      setMessages(
        history.map((item) => ({ role: item.role, content: item.content })),
      );
    } catch {
      threadIdRef.current = `web-s${sessionId}`;
      setMessages([]);
    }
  }, []);

  // 全局侧栏点「新对话 / 某条会话」→ 通过 sessionStorage 交接棒 + 事件通知
  const consumeChatAction = useCallback(() => {
    let action:
      | { type: string; sessionId?: number; projectId?: number }
      | null = null;
    try {
      const raw = sessionStorage.getItem("sg-chat-action");
      if (raw) {
        action = JSON.parse(raw) as {
          type: string;
          sessionId?: number;
          projectId?: number;
        };
        sessionStorage.removeItem("sg-chat-action");
      }
    } catch {
      /* ignore */
    }
    if (!action) return;
    if (action.type === "new-chat") startNewChat(action.projectId);
    if (action.type === "open" && action.sessionId) {
      void openSession(action.sessionId);
    }
  }, [startNewChat, openSession]);

  // 跨页跳转进来时：挂载后消费一次交接棒
  useEffect(() => {
    consumeChatAction();
  }, [consumeChatAction]);

  // 人已在聊天页时：侧栏动作通过事件即时送达
  useEffect(() => {
    window.addEventListener(CHAT_ACTION_EVENT, consumeChatAction);
    return () =>
      window.removeEventListener(CHAT_ACTION_EVENT, consumeChatAction);
  }, [consumeChatAction]);

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
    <div className="relative flex h-full min-w-0 flex-1 flex-col bg-white">
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
                    statusLabel={
                      busy && index === messages.length - 1 ? statusLabel : ""
                    }
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
          {/* 空间 + 权限行（仿 WorkBuddy：输入栏下方选择工作空间） */}
          <div className="mt-2 flex items-center gap-3">
            {/* 空间选择器：新对话会存到选中的空间，记忆也按空间隔离 */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setSpaceOpen((v) => {
                    if (!v) void refreshProjects(); // 每次展开都拉最新列表
                    return !v;
                  });
                }}
                aria-expanded={spaceOpen}
                title="选择对话空间：新对话与本轮记忆会归属该空间"
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium text-zinc-500 transition hover:bg-black/[0.04] hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
                </svg>
                {activeSpace ? activeSpace.name : "选择空间"}
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`transition-transform ${spaceOpen ? "rotate-180" : ""}`}>
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>

              {spaceOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setSpaceOpen(false)}
                    aria-hidden
                  />
                  <div className="animate-pop-in absolute bottom-full left-0 z-50 mb-2 w-52 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
                    <div className="px-2.5 py-1.5 text-[11px] font-medium text-zinc-400">
                      对话空间
                    </div>
                    {projects.map((project) => {
                      const checked = project.id === activeProjectId;
                      return (
                        <button
                          key={project.id}
                          type="button"
                          onClick={() => {
                            setActiveProjectId(project.id);
                            setSpaceOpen(false);
                          }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                        >
                          <span className="w-4 shrink-0 text-teal-600">
                            {checked && (
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                <path d="m5 13 4 4L19 7" />
                              </svg>
                            )}
                          </span>
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
                            <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
                          </svg>
                          <span className="min-w-0 flex-1 truncate">{project.name}</span>
                          {Boolean(project.is_default) && (
                            <span className="shrink-0 text-[10px] text-zinc-400">默认</span>
                          )}
                        </button>
                      );
                    })}
                    {projects.length === 0 && (
                      <p className="px-2.5 py-2 text-[11px] text-zinc-400">
                        还没有其他空间，可在下方新建
                      </p>
                    )}

                    {/* 新建空间入口 */}
                    <div className="mt-1 border-t border-black/[0.06] pt-1">
                      {spaceCreating ? (
                        <input
                          autoFocus
                          value={newSpaceName}
                          onChange={(event) => setNewSpaceName(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void handleCreateSpace();
                            if (event.key === "Escape") {
                              setNewSpaceName("");
                              setSpaceCreating(false);
                            }
                          }}
                          onBlur={() => void handleCreateSpace()}
                          placeholder="空间名称，回车确认"
                          className="mx-1 w-[calc(100%-0.5rem)] rounded-lg bg-zinc-50 px-2.5 py-1.5 text-[13px] ring-1 ring-teal-600 outline-none"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => setSpaceCreating(true)}
                          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] font-medium text-teal-700 transition hover:bg-black/[0.04]"
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="M12 5v14M5 12h14" />
                          </svg>
                          新建空间
                        </button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* 权限开关：允许完全访问（开 = 敏感操作自动同意） */}
            <button
              type="button"
              onClick={toggleFullAccess}
              title={
                fullAccess
                  ? "已开启：保存笔记等操作自动同意，不再逐次询问。点击关闭。"
                  : "已关闭：保存笔记等敏感操作需要你逐次确认。点击开启「允许完全访问」。"
              }
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                fullAccess
                  ? "bg-red-50 text-red-600 hover:bg-red-100"
                  : "text-zinc-400 hover:bg-black/[0.04] hover:text-zinc-600"
              }`}
            >
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v4l2.5 2.5" />
              </svg>
              {fullAccess ? "允许完全访问" : "逐步确认"}
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
  statusLabel,
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
  statusLabel?: string;
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
          {/* 状态行：让等待过程可见（理解问题 / 检索知识库…） */}
          {busy && statusLabel && (
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-teal-700">
              <span className="flex gap-0.5">
                <span className="h-1 w-1 animate-bounce rounded-full bg-teal-600 [animation-delay:0ms]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-teal-600 [animation-delay:120ms]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-teal-600 [animation-delay:240ms]" />
              </span>
              {statusLabel}
            </div>
          )}
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
