"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, DragEvent, KeyboardEvent } from "react";

import {
  addFeedback,
  addNote,
  attachmentRawUrl,
  chatActivity,
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
  uploadChatAttachment,
  type AttachmentMeta,
  type AgentStep,
  type ChatActivityDay,
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
  /** 用户消息携带的附件（用于展示与点击预览） */
  attachments?: AttachmentMeta[];
  /** 助手消息的过程步骤（思考 / 工具调用） */
  steps?: AgentStep[];
  /** 该轮开始时间戳，用于展示「已处理 40s」 */
  startedAt?: number;
}

interface PendingInterrupt {
  library: string;
  title: string;
  preview: string;
}

/* 首屏品牌图标下不再有副标题/快捷区——欢迎区只保留数据卡片与提问热力图 */

/* 首屏课程空间引导的常用课程（大学生视角的直觉分类） */
const COURSE_PRESETS = ["高等数学", "线性代数", "大学物理", "四六级", "数据结构"];

/** 耗时展示：42s / 1m42s（对齐 WorkBuddy 的「已处理 1m42s」） */
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest > 0 ? `${minutes}m${rest}s` : `${minutes}m`;
}

/* 提问热力图：GitHub 式方格，颜色深浅 = 当天提问次数 */
const ASK_LEVELS = [
  "bg-black/[0.05]",
  "bg-teal-200",
  "bg-teal-500",
  "bg-teal-700",
];

function askLevel(questions: number): number {
  if (questions <= 0) return 0;
  if (questions <= 2) return 1;
  if (questions <= 5) return 2;
  return 3;
}

function askDayLabel(date: string): string {
  const [, month, day] = date.split("-");
  return `${Number(month)}月${Number(day)}日`;
}

/** GitHub 式提问热力图：列 = 周，行 = 周一~周日，末列收在今天。 */
function AskHeatmap({ series }: { series: ChatActivityDay[] }) {
  if (series.length === 0) return null;

  // 按周一开头补齐前导空位，切成周列
  const leading = (new Date(`${series[0].date}T00:00:00`).getDay() + 6) % 7;
  const cells: (ChatActivityDay | null)[] = [
    ...Array.from({ length: leading }, () => null as ChatActivityDay | null),
    ...series,
  ];

  const totalQuestions = series.reduce((sum, day) => sum + day.questions, 0);
  const activeDays = series.filter((day) => day.questions > 0).length;

  return (
    <div className="inline-block rounded-3xl bg-black/[0.03] px-8 py-6 text-left">
      <div className="mb-3 flex items-baseline justify-between gap-8">
        <span className="text-xs text-zinc-400">近 12 周提问频率</span>
        <span className="text-xs tabular-nums text-zinc-400">
          共 {totalQuestions} 次 · {activeDays} 天活跃
        </span>
      </div>
      <div
        className="grid w-fit grid-flow-col grid-rows-7 gap-1"
        aria-label="提问频率热力图"
      >
        {cells.map((day, index) =>
          day ? (
            <div
              key={day.date}
              title={`${askDayLabel(day.date)} · 提问 ${day.questions} 次`}
              className={`h-[13px] w-[13px] rounded-[3px] transition-transform hover:scale-125 ${
                ASK_LEVELS[askLevel(day.questions)]
              }`}
            />
          ) : (
            <div key={`blank-${index}`} className="h-[13px] w-[13px]" />
          ),
        )}
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-zinc-300">
        少
        {ASK_LEVELS.map((color) => (
          <span
            key={color}
            className={`h-[10px] w-[10px] rounded-[3px] ${color}`}
          />
        ))}
        多
      </div>
    </div>
  );
}

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
  const [askSeries, setAskSeries] = useState<ChatActivityDay[]>([]);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  // 聊天附件：待发送的文件（已上传拿到 id），随下一条消息一起发出
  const [pendingFiles, setPendingFiles] = useState<AttachmentMeta[]>([]);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [preview, setPreview] = useState<AttachmentMeta | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  /* ---------- 课程空间（会话与记忆按课程隔离） ---------- */
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [spaceOpen, setSpaceOpen] = useState(false);
  const [spaceCreating, setSpaceCreating] = useState(false);
  const [newSpaceName, setNewSpaceName] = useState("");
  // 「＋ 新对话」：先选课程再开新对话（不再自动分配默认空间）
  const [coursePickerOpen, setCoursePickerOpen] = useState(false);
  // 首次使用引导：一个课程都没有时展示常用课程一键创建
  const [courseName, setCourseName] = useState("");
  const [courseError, setCourseError] = useState("");
  const [creatingCourse, setCreatingCourse] = useState(false);
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

  // 「未归类」是系统兜底空间（不在课程选择器里出现）
  const courses = useMemo(
    () => projects.filter((project) => !project.is_default),
    [projects],
  );

  // 只有一个课程时直接选中，省一次点击；有多个则等用户选（必须显式选课程）
  useEffect(() => {
    if (activeProjectId !== null || courses.length !== 1) return;
    setActiveProjectId(courses[0].id);
  }, [courses, activeProjectId]);

  const activeSpace = projects.find((p) => p.id === activeProjectId);

  const createCourse = useCallback(
    async (rawName: string) => {
      const name = rawName.trim();
      if (!name) return null;
      setCourseError("");
      try {
        const created = await createProject(name);
        await refreshProjects();
        notifyChatsChanged();
        return created;
      } catch (err) {
        setCourseError((err as Error).message);
        return null;
      }
    },
    [refreshProjects],
  );

  /** 在一个课程里开一段全新对话（清空当前上下文） */
  const beginNewChatInCourse = useCallback((projectId: number) => {
    setActiveProjectId(projectId);
    sessionIdRef.current = null;
    threadIdRef.current = "";
    setMessages([]);
    setPending(null);
    setSelected([]);
    setPendingFiles([]);
    setStatusLabel("");
    setActionFeedback({});
    setExpandedMsg(null);
    setCoursePickerOpen(false);
  }, []);

  /** 「＋ 新对话」：没有课程先去建，有课程则选一个 */
  const startNewConversation = useCallback(() => {
    if (courses.length === 0) {
      setCoursePickerOpen(true);
      return;
    }
    if (courses.length === 1) {
      beginNewChatInCourse(courses[0].id);
      return;
    }
    setCoursePickerOpen(true);
  }, [courses, beginNewChatInCourse]);

  /** 引导页一键创建常用课程 */
  const handleCreateCourseFromOnboarding = useCallback(
    async (name: string) => {
      setCreatingCourse(true);
      const created = await createCourse(name);
      setCreatingCourse(false);
      if (created) {
        setCourseName("");
        beginNewChatInCourse(created.id);
      }
    },
    [createCourse, beginNewChatInCourse],
  );

  /** 下拉里直接新建课程：成功后自动选中它 */
  const handleCreateSpace = useCallback(async () => {
    const created = await createCourse(newSpaceName);
    setNewSpaceName("");
    setSpaceCreating(false);
    if (created) {
      setActiveProjectId(created.id);
    }
  }, [newSpaceName, createCourse]);

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

  const refreshAskActivity = useCallback(async () => {
    try {
      setAskSeries(await chatActivity(84));
    } catch {
      // 后端未启动时忽略。
    }
  }, []);

  useEffect(() => {
    void refreshLibraries();
    void refreshPlan();
    void refreshAskActivity();
    getHealth()
      .then((h) => setProvider(h.provider))
      .catch(() => setProvider(""));
  }, [refreshLibraries, refreshPlan, refreshAskActivity]);

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
      } else if (event.type === "step") {
        // 过程步骤（思考 / 工具调用）挂到当前这条助手消息上，按 WorkBuddy 式过程流展示
        setMessages((prev) => {
          if (prev.length === 0) return prev;
          const next = [...prev];
          const last = { ...next[next.length - 1] };
          last.steps = [
            ...(last.steps ?? []),
            { kind: event.kind, title: event.title, detail: event.detail },
          ];
          next[next.length - 1] = last;
          return next;
        });
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
      if (!text || busy || uploadingCount > 0) return;
      // 课程空间必选：没选课程先让用户选/建
      if (activeProjectId === null) {
        setCoursePickerOpen(true);
        return;
      }
      setInput("");
      setPickerOpen(false);
      setPlusMenuOpen(false);
      if (inputRef.current) inputRef.current.style.height = "auto";
      setBusy(true);
      busyRef.current = true;
      setStatusLabel("正在理解问题…");
      startPump();
      const attached = pendingFiles;
      const attachedIds = pendingFiles.map((file) => file.id);
      setPendingFiles([]);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text, attachments: attached },
        { role: "assistant", content: "", steps: [], startedAt: Date.now() },
      ]);
      await streamChat(
        {
          message: text,
          thread_id: getThreadId(),
          knowledge_bases: selected,
          session_id: sessionIdRef.current ?? undefined,
          project_id: activeProjectId ?? undefined,
          attachment_ids: attachedIds.length > 0 ? attachedIds : undefined,
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
      pendingFiles,
      uploadingCount,
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
      if (busyRef.current) return;
      if (projectId !== undefined) {
        // 侧栏在某个课程下点「＋」→ 直接在该课程开新对话
        beginNewChatInCourse(projectId);
        return;
      }
      // 没有指定课程 → 交给「新对话」流程（选课程 / 首次引导建课程）
      startNewConversation();
    },
    [beginNewChatInCourse, startNewConversation],
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
        history.map((item) => ({
          role: item.role,
          content: item.content,
          attachments: item.attachments ?? [],
          steps: item.steps ?? [],
        })),
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

  /* ---------- 聊天附件上传（选文件 / 粘贴 / 拖拽共用一条路） ---------- */
  const ACCEPTED_FILES = ".pdf,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp";

  const uploadFile = useCallback(
    async (file: File) => {
      if (pendingFiles.length >= 6) {
        window.alert("一条消息最多带 6 个附件");
        return;
      }
      setUploadingCount((count) => count + 1);
      try {
        const uploaded = await uploadChatAttachment(
          file,
          sessionIdRef.current ?? undefined,
          activeProjectId ?? undefined,
        );
        setPendingFiles((prev) => [
          ...prev,
          {
            id: uploaded.id,
            name: uploaded.filename,
            kind: uploaded.kind === "image" ? "image" : "file",
          },
        ]);
      } catch (error) {
        window.alert(
          error instanceof Error ? error.message : "附件上传失败，请重试",
        );
      } finally {
        setUploadingCount((count) => count - 1);
      }
    },
    [pendingFiles.length, activeProjectId],
  );

  const uploadManyFiles = (files: File[]) =>
    // 并行上传：多选 / 多张截图时不用一个等一个
    Promise.allSettled(files.map((file) => uploadFile(file)));

  const handleFileChosen = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = ""; // 允许重复选同一个文件
    if (files.length === 0) return;
    void uploadManyFiles(files);
  };

  // 截图 / 复制文件后直接 Ctrl(Cmd)+V 粘贴进输入框
  const handlePasteFiles = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length === 0) return; // 纯文本粘贴走原路径
    event.preventDefault();
    void uploadManyFiles(files);
  };

  // 把文件拖进输入栏也能传
  const [dragActive, setDragActive] = useState(false);

  const handleDropFiles = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length === 0) return;
    void uploadManyFiles(files);
  };

  // 预览浮层：Esc 关闭
  useEffect(() => {
    if (!preview) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setPreview(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [preview]);

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
          [index]: "已生成 3 道练习题，到「错题练习」页作答",
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
      {/* 顶部：标题 + 新对话（当前会话所属课程） */}
      <header className="flex items-start justify-between gap-3 px-6 pt-6 pb-2">
        <div className="min-w-0">
          <h1 className="text-[17px] font-bold tracking-tight">AI 对话</h1>
          <p className="mt-0.5 truncate text-xs text-zinc-400">
            {activeSpace && !activeSpace.is_default
              ? `课程：${activeSpace.name}`
              : "还没有选择课程空间"}
            {selected.length > 0 && ` · 检索限定：${selected.join("、")}`}
          </p>
        </div>
        <button
          type="button"
          onClick={startNewConversation}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-teal-600 px-3.5 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98]"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden>
            <path d="M12 5v14M5 12h14" />
          </svg>
          新对话
        </button>
      </header>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        onScroll={onScrollChange}
        className="flex-1 overflow-y-auto px-6 pb-40"
      >
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 ? (
            courses.length === 0 ? (
              /* ---------- 首次使用：先建一个课程空间 ---------- */
              <div className="mx-auto mt-16 max-w-md rounded-2xl border border-black/[0.06] bg-white p-6 text-center shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                <svg
                  width="34"
                  height="34"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#0f766e"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                  className="mx-auto"
                >
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
                </svg>
                <h2 className="mt-3 text-[15px] font-semibold text-zinc-900">
                  先建一个课程空间
                </h2>
                <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">
                  对话、笔记与记忆都按课程隔离——「高等数学」的问题不会串到「大学物理」里
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {COURSE_PRESETS.map((name) => (
                    <button
                      key={name}
                      type="button"
                      disabled={creatingCourse}
                      onClick={() => void handleCreateCourseFromOnboarding(name)}
                      className="rounded-full bg-black/[0.04] px-3.5 py-1.5 text-xs text-zinc-700 transition hover:bg-teal-600/10 hover:text-teal-800 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40"
                    >
                      {name}
                    </button>
                  ))}
                </div>
                <div className="mt-4 flex gap-2">
                  <input
                    value={courseName}
                    onChange={(event) => setCourseName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && courseName.trim()) {
                        void handleCreateCourseFromOnboarding(courseName);
                      }
                    }}
                    maxLength={64}
                    placeholder="或自己填一个课程名"
                    className="min-w-0 flex-1 rounded-full bg-white px-4 py-2 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
                  />
                  <button
                    type="button"
                    disabled={!courseName.trim() || creatingCourse}
                    onClick={() => void handleCreateCourseFromOnboarding(courseName)}
                    className="shrink-0 rounded-full bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-40"
                  >
                    创建并开始
                  </button>
                </div>
                {courseError && (
                  <p className="mt-2 text-xs text-red-600">{courseError}</p>
                )}
              </div>
            ) : (
            /* ---------- 极简欢迎首屏：品牌 + 数据卡片 + 提问热力图 ---------- */
            <div className="mt-16 flex flex-col items-center">
              <svg
                width="52"
                height="52"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#0f766e"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <circle cx="5" cy="19" r="2.2" />
                <circle cx="12" cy="5" r="2.2" />
                <circle cx="19" cy="19" r="2.2" />
                <path d="M6.5 17.2 10.6 7.4" />
                <path d="m13.4 7.4 4.1 9.8" />
                <path d="M7.2 19h9.6" />
              </svg>
              <h2 className="mt-5 text-2xl font-bold tracking-tight">
                你好，我是 StudyGraph
              </h2>

              {/* 轻量学习数据概览：数字为核心，标签弱化 */}
              <div className="mx-auto mt-10 grid max-w-xl grid-cols-3 gap-4">
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
                    className="rounded-2xl bg-black/[0.03] px-4 py-6 transition hover:bg-black/[0.06] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    <div className="text-[32px] font-bold leading-none tracking-tight text-zinc-800 tabular-nums">
                      {stat.value}
                    </div>
                    <div className="mt-2 text-xs text-zinc-400">
                      {stat.label}
                    </div>
                  </Link>
                ))}
              </div>

              {/* 提问热力图（GitHub 式，按提问频率统计） */}
              <div className="mt-10">
                <AskHeatmap series={askSeries} />
              </div>
            </div>
            )
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
                    onPreviewAttachment={(file) => setPreview(file)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 附件图片预览浮层 */}
      {preview && preview.kind === "image" && (
        <div
          className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-black/70 p-6"
          onClick={() => setPreview(null)}
        >
          <img
            src={attachmentRawUrl(preview.id)}
            alt={preview.name}
            className="max-h-[80vh] max-w-full rounded-lg object-contain shadow-2xl"
          />
          <div className="mt-3 flex items-center gap-3 text-xs text-white/80">
            <span className="max-w-[60vw] truncate">{preview.name}</span>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="rounded-full bg-white/15 px-3 py-1 transition hover:bg-white/25"
            >
              关闭（Esc）
            </button>
          </div>
        </div>
      )}

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
          {/* + 功能菜单 */}
          {plusMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setPlusMenuOpen(false)}
                aria-hidden
              />
              <div className="animate-pop-in absolute bottom-full left-0 z-50 mb-2 w-56 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
                <button
                  type="button"
                  onClick={() => {
                    setPlusMenuOpen(false);
                    fileInputRef.current?.click();
                  }}
                  disabled={uploadingCount > 0}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04] disabled:opacity-50"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                  {uploadingCount > 0 ? "正在上传…" : "上传文件（PDF/图片/文本）"}
                </button>
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
                {/* 权限开关：允许完全访问（开 = 敏感操作自动同意），收纳进菜单 */}
                <div className="mt-1 border-t border-black/[0.06] pt-1">
                  <button
                    type="button"
                    onClick={toggleFullAccess}
                    title={
                      fullAccess
                        ? "已开启：保存笔记等操作自动同意，不再逐次询问。点击关闭。"
                        : "已关闭：保存笔记等敏感操作需要你逐次确认。点击开启「允许完全访问」。"
                    }
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition hover:bg-black/[0.04]"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
                      <rect x="4" y="10" width="16" height="10" rx="2" />
                      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                    </svg>
                    <span
                      className={`min-w-0 flex-1 ${
                        fullAccess ? "text-red-600" : "text-zinc-700"
                      }`}
                    >
                      允许完全访问
                    </span>
                    <span
                      className={`relative h-4 w-7 shrink-0 rounded-full transition ${
                        fullAccess ? "bg-red-500" : "bg-black/[0.15]"
                      }`}
                      aria-hidden
                    >
                      <span
                        className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${
                          fullAccess ? "left-3.5" : "left-0.5"
                        }`}
                      />
                    </span>
                  </button>
                </div>
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

          {/* 待发送附件条（上传中也有可见反馈） */}
          {(pendingFiles.length > 0 || uploadingCount > 0) && (
            <div className="animate-fade-up mb-2 flex flex-wrap gap-1.5">
              {pendingFiles.map((file) => (
                <span
                  key={file.id}
                  className="flex items-center gap-1.5 rounded-full bg-white py-1 pl-1 pr-2 text-[11px] text-zinc-600 shadow-sm ring-1 ring-black/10"
                >
                  {file.kind === "image" ? (
                    <button
                      type="button"
                      title="点击预览大图"
                      onClick={() => setPreview(file)}
                      className="h-6 w-6 overflow-hidden rounded-full ring-1 ring-black/10 transition hover:ring-teal-600"
                    >
                      <img
                        src={attachmentRawUrl(file.id)}
                        alt={file.name}
                        className="h-full w-full object-cover"
                      />
                    </button>
                  ) : (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="ml-1 shrink-0 text-zinc-400">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                      <path d="M14 2v6h6" />
                    </svg>
                  )}
                  <span className="max-w-[140px] truncate">{file.name}</span>
                  <button
                    type="button"
                    title="移除附件"
                    onClick={() =>
                      setPendingFiles((prev) =>
                        prev.filter((item) => item.id !== file.id),
                      )
                    }
                    className="text-zinc-400 transition hover:text-red-600"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              ))}
              {uploadingCount > 0 && (
                <span className="flex items-center gap-1.5 rounded-full bg-teal-600/10 px-2.5 py-1 text-[11px] font-medium text-teal-700">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-teal-600/30 border-t-teal-600" />
                  正在上传{uploadingCount > 1 ? ` ${uploadingCount} 个文件` : "…"}
                </span>
              )}
            </div>
          )}

          {/* 隐藏的文件选择器（+ 菜单「上传文件」触发） */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILES}
            onChange={(event) => void handleFileChosen(event)}
            className="hidden"
          />

          {/* 输入栏（支持把文件直接拖进来） */}
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDropFiles}
            className={`flex items-end gap-1.5 rounded-2xl bg-white p-2 shadow-lg shadow-black/[0.06] ring-1 transition focus-within:ring-2 focus-within:ring-teal-600 ${
              dragActive ? "ring-2 ring-teal-600" : "ring-black/10"
            }`}
          >
            <button
              type="button"
              onClick={() => setPlusMenuOpen((v) => !v)}
              aria-expanded={plusMenuOpen}
              aria-label="更多功能"
              title={fullAccess ? "允许完全访问已开启" : undefined}
              className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none ${
                plusMenuOpen
                  ? "bg-black/[0.06] text-zinc-900"
                  : "text-zinc-500 hover:bg-black/[0.06]"
              }`}
            >
              {fullAccess && (
                <span
                  className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-red-500"
                  aria-hidden
                />
              )}
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
              onPaste={handlePasteFiles}
              rows={1}
              placeholder="输入你的问题，或粘贴 / 拖入 PDF、图片、文件…"
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
              disabled={busy || uploadingCount > 0 || !input.trim()}
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
                {activeSpace && !activeSpace.is_default ? activeSpace.name : "选择课程"}
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
                      选择课程空间
                    </div>
                    {courses.map((project) => {
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
                    {courses.length === 0 && (
                      <p className="px-2.5 py-2 text-[11px] text-zinc-400">
                        还没有课程空间，可在下方新建
                      </p>
                    )}

                    {/* 新建课程入口 */}
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
                          placeholder="课程名称，回车确认"
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
                          新建课程
                        </button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

          </div>
          <p className="mt-2 text-center text-[10px] text-zinc-300">
            内容由 AI 生成，请核实重要信息
          </p>
        </div>
      </div>

      {/* 新对话：先选课程空间（会话与记忆按课程隔离） */}
      {coursePickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 px-4">
          <div className="animate-pop-in w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold tracking-tight">选择课程空间</h2>
              <button
                type="button"
                onClick={() => setCoursePickerOpen(false)}
                aria-label="关闭"
                className="grid h-7 w-7 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              新对话归属哪个课程？记忆与笔记会跟着这个课程走。
            </p>

            <div className="mt-3 max-h-56 space-y-1 overflow-y-auto">
              {courses.map((course) => (
                <button
                  key={course.id}
                  type="button"
                  onClick={() => beginNewChatInCourse(course.id)}
                  className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-[13px] text-zinc-700 transition hover:bg-teal-600/[0.08] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
                  </svg>
                  <span className="min-w-0 flex-1 truncate">{course.name}</span>
                  {course.id === activeProjectId && (
                    <span className="shrink-0 text-[10px] text-teal-700">当前</span>
                  )}
                </button>
              ))}
              {courses.length === 0 && (
                <p className="px-3 py-3 text-xs text-zinc-400">
                  还没有课程空间，先在下面建一个
                </p>
              )}
            </div>

            <div className="mt-3 border-t border-black/[0.06] pt-3">
              <div className="flex gap-2">
                <input
                  value={courseName}
                  onChange={(event) => setCourseName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && courseName.trim()) {
                      void handleCreateCourseFromOnboarding(courseName);
                    }
                  }}
                  maxLength={64}
                  placeholder="新建课程，例如：离散数学"
                  className="min-w-0 flex-1 rounded-xl bg-zinc-50 px-3.5 py-2 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
                />
                <button
                  type="button"
                  disabled={!courseName.trim() || creatingCourse}
                  onClick={() => void handleCreateCourseFromOnboarding(courseName)}
                  className="shrink-0 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-40"
                >
                  创建
                </button>
              </div>
              {courseError && (
                <p className="mt-2 text-xs text-red-600">{courseError}</p>
              )}
            </div>
          </div>
        </div>
      )}

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
  onPreviewAttachment,
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
  onPreviewAttachment: (file: AttachmentMeta) => void;
}) {
  const steps = message.steps ?? [];
  // 流式进行中默认展开过程，结束后折叠；用户手动切换后以用户选择为准
  const [traceOverride, setTraceOverride] = useState<boolean | null>(null);
  const traceOpen = traceOverride ?? busy;
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!busy || !message.startedAt) return;
    // 只在定时器回调里 setState（每秒一跳），避免在 effect 体内同步 setState
    const timer = window.setInterval(() => {
      if (message.startedAt) {
        setElapsed(Math.round((Date.now() - message.startedAt) / 1000));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy, message.startedAt]);

  const elapsedLabel = elapsed > 0 ? `已处理 ${formatDuration(elapsed)}` : "";

  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1">
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex max-w-[85%] flex-wrap justify-end gap-1">
            {message.attachments.map((file) => (
              <span
                key={file.id}
                className="flex items-center gap-1.5 rounded-full bg-black/[0.05] py-1 pl-1 pr-2.5 text-[11px] text-zinc-600"
              >
                {file.kind === "image" ? (
                  <button
                    type="button"
                    title="点击预览大图"
                    onClick={() => onPreviewAttachment(file)}
                    className="h-7 w-7 overflow-hidden rounded-full ring-1 ring-black/10 transition hover:ring-teal-600"
                  >
                    <img
                      src={attachmentRawUrl(file.id)}
                      alt={file.name}
                      className="h-full w-full object-cover"
                    />
                  </button>
                ) : (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="ml-1 shrink-0 text-zinc-400">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                    <path d="M14 2v6h6" />
                  </svg>
                )}
                <span className="max-w-[160px] truncate">{file.name}</span>
              </span>
            ))}
          </div>
        )}
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
        {/* WorkBuddy 式过程卡片：头部（名称/耗时）→ 思考与工具步骤 → 最终回答 */}
        <div className="overflow-hidden rounded-2xl rounded-tl-lg bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] ring-1 ring-black/[0.04]">
          {/* 头部 */}
          <div className="flex items-center gap-2 px-4 pt-3">
            <span className="text-[13px] font-semibold text-zinc-900">
              StudyGraph 智能体
            </span>
            {elapsedLabel && (
              <span className="text-[11px] text-zinc-400">{elapsedLabel}</span>
            )}
            {steps.length > 0 && (
              <button
                type="button"
                onClick={() => setTraceOverride(!traceOpen)}
                className="ml-auto text-[11px] text-zinc-400 transition hover:text-zinc-600"
              >
                {traceOpen ? "收起过程" : `查看过程（${steps.length}）`}
              </button>
            )}
          </div>

          {/* 过程流：思考 / 工具调用 */}
          {steps.length > 0 && traceOpen && (
            <div className="mt-2 space-y-2 px-4">
              {steps.map((step, i) =>
                step.kind === "thinking" ? (
                  <div key={`${step.title}-${i}`}>
                    <button
                      type="button"
                      onClick={() => setThinkingOpen((v) => !v)}
                      className="flex items-center gap-1.5 text-left text-[12px] font-medium text-zinc-500 transition hover:text-zinc-700"
                    >
                      <svg
                        width="10"
                        height="10"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                        className={`shrink-0 text-zinc-400 transition-transform ${
                          thinkingOpen ? "" : "-rotate-90"
                        }`}
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                      {step.title}
                    </button>
                    {thinkingOpen && step.detail && (
                      <p className="mt-1 whitespace-pre-wrap rounded-lg bg-black/[0.03] px-3 py-2 text-[12px] leading-relaxed text-zinc-500">
                        {step.detail}
                      </p>
                    )}
                  </div>
                ) : (
                  <div
                    key={`${step.title}-${i}`}
                    className="flex items-start gap-1.5 text-[12px] text-zinc-500"
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
                      className="mt-[3px] shrink-0 text-teal-600"
                    >
                      <path d="m14 4 6 6L9 21H3v-6Z" />
                      <path d="m12 6 6 6" />
                    </svg>
                    <span className="min-w-0">
                      <span className="font-medium text-zinc-600">
                        {step.title}
                      </span>
                      {step.detail && (
                        <span className="text-zinc-400"> · {step.detail}</span>
                      )}
                    </span>
                  </div>
                ),
              )}
            </div>
          )}

          {/* 回答正文 */}
          <div className="px-4 pb-3 pt-2.5">
            {/* 流式进行中的等待行 */}
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
              <div className="prose prose-zinc max-w-none text-sm leading-relaxed">
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
