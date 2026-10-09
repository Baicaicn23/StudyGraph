"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  addNote,
  createLibrary,
  deleteDocument,
  deleteLibrary,
  getHealth,
  listDocuments,
  listLibraries,
  streamChat,
  uploadDocument,
  type DocumentItem,
  type Library,
  type StreamEvent,
} from "@/lib/api";
import Markdown from "@/components/Markdown";
import { buttonClass, inputClass, Notice } from "@/components/ui";

function FolderIcon({ active }: { active?: boolean }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={active ? "text-teal-600" : "text-zinc-400"}
    >
      <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9L9.6 3.9A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
    </svg>
  );
}

function DocIcon({ className }: { className?: string }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6M16 13H8M16 17H8" />
    </svg>
  );
}

function formatDay(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleDateString("zh-CN", {
    month: "numeric",
    day: "numeric",
  });
}

interface QaMessage {
  role: "user" | "assistant";
  content: string;
}

const QUICK_ASKS = ["总结这个知识点", "解释重点难点", "出 3 道练习题"];

/* ================= AI 问答面板（桌面侧栏 / 移动抽屉共用） ================= */

function QaPanel({
  activeLib,
  messages,
  busy,
  input,
  modelLabel,
  copiedIndex,
  onInputChange,
  onSend,
  onQuickFill,
  onCopy,
  onSummarize,
  onGenPractice,
  onClose,
}: {
  activeLib: string;
  messages: QaMessage[];
  busy: boolean;
  input: string;
  modelLabel: string;
  copiedIndex: number | null;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onQuickFill: (text: string) => void;
  onCopy: (index: number) => void;
  onSummarize: () => void;
  onGenPractice: () => void;
  onClose?: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  return (
    <>
      {/* 标题栏 */}
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-bold tracking-tight">知识库AI问答</h2>
          <p className="mt-0.5 truncate text-xs text-zinc-400">
            当前检索：{activeLib || "未选择"}
            {modelLabel ? ` · ${modelLabel}` : ""}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="收起问答栏"
            className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
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
            >
              <path d="M11 19l-7-7 7-7M19 19l-7-7 7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto bg-black/[0.02] px-4 py-4"
      >
        {messages.length === 0 ? (
          <div className="mt-14 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-zinc-400 shadow-sm ring-1 ring-black/[0.05]">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
              </svg>
            </div>
            <p className="mt-3 text-sm text-zinc-500">基于当前知识库提问</p>
            <div className="mt-4 flex flex-wrap justify-center gap-1.5">
              {QUICK_ASKS.map((text) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => onQuickFill(text)}
                  className="rounded-full bg-white px-3 py-1.5 text-[11px] text-zinc-600 shadow-sm ring-1 ring-black/[0.06] transition hover:text-teal-700 hover:ring-teal-600/40 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) =>
            msg.role === "user" ? (
              <div key={index} className="flex justify-end">
                <div className="animate-fade-up max-w-[85%] rounded-2xl rounded-br-md bg-teal-600 px-3.5 py-2 text-sm leading-relaxed text-white">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div key={index} className="animate-fade-up">
                <div className="rounded-2xl bg-white px-3.5 py-3 shadow-sm ring-1 ring-black/[0.05]">
                  <div className="prose prose-zinc max-w-none text-sm">
                    <Markdown content={msg.content} />
                  </div>
                  {msg.content && !busy && (
                    <div className="mt-2 flex items-center gap-3 border-t border-black/[0.05] pt-2">
                      <button
                        type="button"
                        onClick={() => onCopy(index)}
                        className="text-[11px] font-medium text-teal-700 transition hover:brightness-110"
                      >
                        {copiedIndex === index ? "已复制" : "复制"}
                      </button>
                      <button
                        type="button"
                        onClick={onSummarize}
                        className="text-[11px] font-medium text-teal-700 transition hover:brightness-110"
                      >
                        总结全文
                      </button>
                      <button
                        type="button"
                        onClick={onGenPractice}
                        className="text-[11px] font-medium text-teal-700 transition hover:brightness-110"
                      >
                        生成练习题
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          )
        )}
      </div>

      {/* 输入区 */}
      <div className="border-t border-black/[0.06] p-3">
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          rows={2}
          placeholder="基于当前知识库提问..."
          className="w-full resize-none rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
        />
        <div className="mt-2 flex items-center gap-2">
          {modelLabel && (
            <span className="inline-flex items-center gap-1 rounded-full border border-black/[0.08] px-2 py-0.5 text-[10px] font-medium text-zinc-500">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  modelLabel === "Mock 模型" ? "bg-zinc-300" : "bg-teal-600"
                }`}
              />
              {modelLabel}
            </span>
          )}
          <span className="flex-1" />
          <button
            type="button"
            onClick={onSend}
            disabled={busy || !input.trim() || !activeLib}
            aria-label="发送"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none active:scale-95 disabled:opacity-25"
          >
            {busy ? (
              <span className="block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
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
              >
                <path d="m3 11 18-8-7 18-2.5-7.5L3 11Z" />
              </svg>
            )}
          </button>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-zinc-300">
          内容由AI生成仅供参考
        </p>
      </div>
    </>
  );
}

/* ================= 页面 ================= */

export default function KnowledgePage() {
  const router = useRouter();
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [libDocs, setLibDocs] = useState<Record<string, DocumentItem[]>>({});
  const [activeLib, setActiveLib] = useState("");
  const [expandedLibs, setExpandedLibs] = useState<string[]>([]);
  const [treeSearch, setTreeSearch] = useState("");

  const [panel, setPanel] = useState<"upload" | "note" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");

  // AI 问答
  const [qaOpen, setQaOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [qaMessages, setQaMessages] = useState<QaMessage[]>([]);
  const [qaInput, setQaInput] = useState("");
  const [qaBusy, setQaBusy] = useState(false);
  const [provider, setProvider] = useState("");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const qaThreadRef = useRef("");
  const qaInputRef = useRef<HTMLTextAreaElement | null>(null);

  // AI 问答栏宽度（可拖拽调节，本地记忆）
  const [qaWidth, setQaWidth] = useState(384);
  const [isDragging, setIsDragging] = useState(false);

  // 选中文本 → 向 AI 提问
  const [selBtn, setSelBtn] = useState<{
    x: number;
    y: number;
    text: string;
  } | null>(null);

  const refreshLibraries = useCallback(async () => {
    try {
      const bases = await listLibraries();
      setLibraries(bases);
      setActiveLib((current) => current || bases[0]?.name || "");
      setExpandedLibs((current) =>
        current.length > 0 ? current : bases.slice(0, 1).map((b) => b.name),
      );
      const entries = await Promise.all(
        bases.map(
          async (base) =>
            [base.name, await listDocuments(base.name).catch(() => [])] as const,
        ),
      );
      setLibDocs(Object.fromEntries(entries));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshLibraries();
    getHealth()
      .then((h) => setProvider(h.provider))
      .catch(() => setProvider(""));
    // 恢复上次调整的问答栏宽度
    try {
      const saved = Number(localStorage.getItem("studygraph-qa-width"));
      if (saved >= 320 && saved <= 720) setQaWidth(saved);
    } catch {
      /* ignore */
    }
  }, [refreshLibraries]);

  const startQaDrag = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = qaWidth;
    const minWidth = 320;
    const maxWidth = Math.min(window.innerWidth * 0.5, 720);
    let latest = startWidth;
    setIsDragging(true);
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    const onMove = (move: MouseEvent) => {
      let next = startWidth + (startX - move.clientX);
      if (Math.abs(next - minWidth) < 14) next = minWidth; // 边界阻尼吸附
      if (Math.abs(next - maxWidth) < 14) next = maxWidth;
      latest = Math.max(minWidth, Math.min(maxWidth, next));
      setQaWidth(latest);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      setIsDragging(false);
      try {
        localStorage.setItem("studygraph-qa-width", String(latest));
      } catch {
        /* ignore */
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [qaWidth]);

  const selectLibrary = useCallback((name: string) => {
    setActiveLib(name);
    setExpandedLibs((prev) =>
      prev.includes(name)
        ? prev.filter((item) => item !== name)
        : [...prev, name],
    );
  }, []);

  /* ---------- 右键菜单：新建 / 删除 ---------- */
  const [treeMenu, setTreeMenu] = useState<
    | { x: number; y: number; kind: "lib" | "doc" | "blank"; libName?: string; doc?: DocumentItem }
    | null
  >(null);

  const openTreeMenu = (
    event: React.MouseEvent,
    kind: "lib" | "doc" | "blank",
    data?: { libName?: string; doc?: DocumentItem },
  ) => {
    event.preventDefault();
    event.stopPropagation();
    setTreeMenu({ x: event.clientX, y: event.clientY, kind, ...data });
  };

  const newLibraryViaPrompt = useCallback(async () => {
    setTreeMenu(null);
    const name = window
      .prompt("新建知识库：请输入名称（例如：高等数学）")
      ?.trim();
    if (!name) return;
    try {
      await createLibrary(name);
      await refreshLibraries();
      setActiveLib(name);
      setExpandedLibs((prev) =>
        prev.includes(name) ? prev : [...prev, name],
      );
      setMessage(`已创建知识库「${name}」`);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [refreshLibraries]);

  const deleteLibraryViaMenu = useCallback(
    async (name: string) => {
      setTreeMenu(null);
      const count = (libDocs[name] ?? []).length;
      const ok = window.confirm(
        `确定删除知识库「${name}」吗？${
          count > 0 ? `其中 ${count} 份资料会一起删除，` : ""
        }此操作不可恢复。`,
      );
      if (!ok) return;
      try {
        await deleteLibrary(name);
        setMessage(`已删除知识库「${name}」`);
        if (activeLib === name) setActiveLib("");
        await refreshLibraries();
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [libDocs, activeLib, refreshLibraries],
  );

  const deleteDocumentViaMenu = useCallback(
    async (doc: DocumentItem) => {
      setTreeMenu(null);
      const ok = window.confirm(`确定删除资料《${doc.title}》吗？不可恢复。`);
      if (!ok) return;
      try {
        await deleteDocument(doc.id);
        setMessage(`已删除《${doc.title}》`);
        await refreshLibraries();
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [refreshLibraries],
  );

  const modelLabel = provider === "mock" ? "Mock 模型" : provider;

  /* ---------- AI 问答 ---------- */
  const appendToQa = useCallback((delta: string) => {
    setQaMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant") {
        next[next.length - 1] = { ...last, content: last.content + delta };
      }
      return next;
    });
  }, []);

  const handleQaEvent = useCallback(
    (event: StreamEvent) => {
      if (event.type === "token") appendToQa(event.content);
      else if (event.type === "interrupt")
        appendToQa("\n\n> 沉淀资料请用「上传 / 写笔记」，这里只做检索问答。");
      else if (event.type === "guard")
        appendToQa(`\n\n> 🚧 护栏提示：${event.reason}`);
      else if (event.type === "error")
        appendToQa(`\n\n> ⚠️ ${event.message}`);
    },
    [appendToQa],
  );

  const sendQa = useCallback(
    async (raw?: string) => {
      const text = (raw ?? qaInput).trim();
      if (!text || qaBusy || !activeLib) return;
      if (!qaThreadRef.current) {
        qaThreadRef.current = `kb-${Math.random().toString(36).slice(2, 10)}`;
      }
      setQaInput("");
      setQaBusy(true);
      setQaMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ]);
      await streamChat(
        {
          message: text,
          thread_id: qaThreadRef.current,
          knowledge_bases: [activeLib],
        },
        handleQaEvent,
      );
      setQaBusy(false);
    },
    [qaInput, qaBusy, activeLib, handleQaEvent],
  );

  const onCopyAnswer = useCallback(
    (index: number) => {
      const msg = qaMessages[index];
      if (msg) void navigator.clipboard.writeText(msg.content);
      setCopiedIndex(index);
      window.setTimeout(() => setCopiedIndex(null), 1500);
    },
    [qaMessages],
  );

  const onSummarize = useCallback(() => {
    void sendQa(
      activeLib ? `请总结「${activeLib}」资料的核心内容与要点` : undefined,
    );
  }, [sendQa, activeLib]);

  const onGenPracticeFromQa = useCallback(() => {
    setQaOpen(true);
    setDrawerOpen(false);
  }, []);

  /* ---------- 上传 / 写笔记 ---------- */
  const onUpload = async () => {
    setError("");
    setMessage("");
    if (!file) {
      setError("请先选择文件（TXT / Markdown / PDF / 图片）");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadDocument(activeLib, file);
      setMessage(
        `已入库到「${activeLib}」：《${result.title}》（${result.chars} 字）`,
      );
      setFile(null);
      setPanel(null);
      await refreshLibraries();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const onAddNote = async () => {
    setError("");
    setMessage("");
    if (!noteTitle.trim() || !noteContent.trim()) {
      setError("请填写标题与正文");
      return;
    }
    setSaving(true);
    try {
      await addNote(activeLib, noteTitle.trim(), noteContent.trim());
      setMessage(`已保存笔记《${noteTitle.trim()}》到「${activeLib}」`);
      setNoteTitle("");
      setNoteContent("");
      setPanel(null);
      await refreshLibraries();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  /* ---------- 选中文字 → 向 AI 提问 ---------- */
  const onContentMouseUp = (event: React.MouseEvent) => {
    const selection = window.getSelection()?.toString().trim();
    if (selection && selection.length > 1) {
      setSelBtn({
        x: event.clientX,
        y: event.clientY,
        text: selection.slice(0, 120),
      });
    } else {
      setSelBtn(null);
    }
  };

  const askAboutSelection = () => {
    if (!selBtn) return;
    setQaInput(`请解释：「${selBtn.text}」`);
    setSelBtn(null);
    setQaOpen(true);
    setDrawerOpen(true);
    window.setTimeout(() => qaInputRef.current?.focus(), 60);
  };

  const active = libraries.find((item) => item.name === activeLib);
  const docs = libDocs[activeLib] ?? [];
  const filteredLibs = libraries.filter(
    (lib) =>
      !treeSearch.trim() ||
      lib.name.toLowerCase().includes(treeSearch.trim().toLowerCase()) ||
      (libDocs[lib.name] ?? []).some((doc) =>
        doc.title.toLowerCase().includes(treeSearch.trim().toLowerCase()),
      ),
  );

  const qaProps = {
    activeLib,
    messages: qaMessages,
    busy: qaBusy,
    input: qaInput,
    modelLabel,
    copiedIndex,
    onInputChange: setQaInput,
    onSend: () => void sendQa(),
    onQuickFill: (text: string) => {
      setQaInput(text);
      qaInputRef.current?.focus();
    },
    onCopy: onCopyAnswer,
    onSummarize,
    onGenPractice: onGenPracticeFromQa,
  };

  return (
    <div className="relative flex h-full bg-white">
      {/* 栏一：目录树 */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-black/[0.06] bg-white lg:flex xl:w-60">
        <div className="px-3 pt-4 pb-2">
          <div className="relative">
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
              value={treeSearch}
              onChange={(event) => setTreeSearch(event.target.value)}
              placeholder="搜索目录…"
              className="w-full rounded-xl bg-black/[0.03] py-1.5 pl-8 pr-3 text-xs outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
            />
          </div>
        </div>
        <div
          className="flex-1 overflow-y-auto px-2 pb-4"
          onContextMenu={(event) => openTreeMenu(event, "blank")}
        >
          {filteredLibs.map((library) => {
            const libActive = library.name === activeLib;
            const isOpen = expandedLibs.includes(library.name);
            const libDocList = libDocs[library.name] ?? [];
            const visibleDocs = treeSearch.trim()
              ? libDocList.filter((doc) =>
                  doc.title
                    .toLowerCase()
                    .includes(treeSearch.trim().toLowerCase()),
                )
              : libDocList;
            return (
              <div
                key={library.name}
                className="mb-0.5"
                onContextMenu={(event) =>
                  openTreeMenu(event, "lib", { libName: library.name })
                }
              >
                <div
                  className={`group relative flex items-center rounded-lg border-l-2 transition ${
                    libActive
                      ? "border-teal-600 bg-teal-50/70"
                      : "border-transparent hover:bg-black/[0.04]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => selectLibrary(library.name)}
                    className={`flex min-w-0 flex-1 items-center gap-2 py-2 pl-2.5 pr-2 text-left text-[13px] transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                      libActive
                        ? "font-semibold text-zinc-900"
                        : "font-medium text-zinc-800"
                    }`}
                  >
                    <FolderIcon active={libActive} />
                    <span className="fade-x min-w-0 flex-1">{library.name}</span>
                    <span className="text-[11px] tabular-nums text-zinc-400">
                      {library.document_count}
                    </span>
                  </button>
                </div>
                {isOpen &&
                  visibleDocs.map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => router.push(`/knowledge/doc/${doc.id}`)}
                      onContextMenu={(event) =>
                        openTreeMenu(event, "doc", { doc })
                      }
                      title={`${doc.title}（右键可删除）`}
                      className="ml-3 flex w-[calc(100%-0.75rem)] items-center gap-2 rounded-lg border-l-2 border-transparent py-1.5 pl-2.5 pr-2 text-left text-xs text-zinc-500 transition hover:bg-black/[0.04] hover:text-zinc-800 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                    >
                      <DocIcon className="shrink-0 text-zinc-400" />
                      <span className="fade-x min-w-0 flex-1">{doc.title}</span>
                    </button>
                  ))}
              </div>
            );
          })}
          {libraries.length === 0 && (
            <p className="px-2.5 py-2 text-xs text-zinc-400">
              还没有学科库。右键这里，或点中间的按钮新建。
            </p>
          )}
        </div>
      </aside>

      {/* 栏二：内容区（浏览列表 / 文档详情） */}
      <section className="flex min-w-0 flex-1 flex-col border-r border-black/[0.06]">
        <header className="border-b border-black/[0.06] px-5 pt-4 pb-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="truncate text-sm font-semibold text-zinc-700">
              {activeLib || "知识库"}
            </h2>
            <div className="flex shrink-0 items-center gap-1.5">
              {!qaOpen && (
                <button
                  type="button"
                  onClick={() => setQaOpen(true)}
                  className="hidden items-center gap-1.5 rounded-full bg-black/[0.05] px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-black/[0.09] xl:inline-flex"
                >
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
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
                  </svg>
                  AI 问答
                </button>
              )}
              <button
                type="button"
                onClick={() => setDrawerOpen(true)}
                disabled={!activeLib}
                className="inline-flex items-center gap-1.5 rounded-full bg-black/[0.05] px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-black/[0.09] disabled:opacity-40 xl:hidden"
              >
                AI 问答
              </button>
              <button
                type="button"
                onClick={() => setPanel(panel === "upload" ? null : "upload")}
                disabled={!activeLib}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40 ${
                  panel === "upload"
                    ? "bg-zinc-900 text-white"
                    : "bg-black/[0.05] text-zinc-700 hover:bg-black/[0.09]"
                }`}
              >
                上传
              </button>
              <button
                type="button"
                onClick={() => setPanel(panel === "note" ? null : "note")}
                disabled={!activeLib}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40 ${
                  panel === "note"
                    ? "bg-zinc-900 text-white"
                    : "bg-black/[0.05] text-zinc-700 hover:bg-black/[0.09]"
                }`}
              >
                写笔记
              </button>
            </div>
          </div>
        </header>

        <div
          className="flex-1 overflow-y-auto px-5 py-4"
          onMouseUp={onContentMouseUp}
          onScroll={() => setSelBtn(null)}
        >
          <div className="mx-auto max-w-2xl space-y-4">
            {message && <Notice kind="ok">{message}</Notice>}
            {error && <Notice kind="error">{error}</Notice>}

            {panel === "upload" && (
              <div className="animate-fade-up rounded-xl bg-black/[0.03] p-4">
                <h3 className="mb-3 text-sm font-semibold">
                  上传到「{activeLib}」（TXT / Markdown / PDF / 图片）
                </h3>
                <input
                  type="file"
                  accept=".txt,.md,.markdown,.pdf,.png,.jpg,.jpeg,.webp"
                  onChange={(event) =>
                    setFile(event.target.files?.[0] ?? null)
                  }
                  className="mb-3 w-full text-sm text-zinc-600 file:mr-3 file:rounded-full file:border-0 file:bg-white file:px-4 file:py-2 file:text-sm file:font-medium file:text-zinc-700 file:ring-1 file:ring-black/10 hover:file:bg-black/[0.04]"
                />
                <button
                  type="button"
                  onClick={() => void onUpload()}
                  disabled={uploading || !file}
                  className={buttonClass}
                >
                  {uploading ? "解析入库中…" : "上传入库"}
                </button>
                <p className="mt-2 text-[11px] leading-relaxed text-zinc-400">
                  图片（PNG / JPG / WebP）会由视觉模型转写成 Markdown
                  笔记后入库，拍照课件、板书都可以；转换需要几秒钟。
                </p>
              </div>
            )}

            {panel === "note" && (
              <div className="animate-fade-up rounded-xl bg-black/[0.03] p-4">
                <h3 className="mb-3 text-sm font-semibold">
                  写笔记到「{activeLib}」
                </h3>
                <div className="space-y-3">
                  <input
                    value={noteTitle}
                    maxLength={200}
                    onChange={(event) => setNoteTitle(event.target.value)}
                    placeholder="标题，例如：特征值与特征向量"
                    className={inputClass}
                  />
                  <textarea
                    value={noteContent}
                    maxLength={200000}
                    onChange={(event) => setNoteContent(event.target.value)}
                    rows={5}
                    placeholder="贴上或写下你的笔记内容…"
                    className={inputClass}
                  />
                  <button
                    type="button"
                    onClick={() => void onAddNote()}
                    disabled={saving}
                    className={buttonClass}
                  >
                    {saving ? "保存中…" : "保存笔记"}
                  </button>
                </div>
              </div>
            )}

            {
              /* 浏览模式：文档列表 */
              <>
                <h2 className="text-lg font-bold tracking-tight">
                  {activeLib || "知识库"}
                  <span className="ml-2 text-xs font-normal text-zinc-400">
                    {active ? `${active.document_count} 份资料` : ""}
                  </span>
                </h2>
                {docs.length === 0 ? (
                  <div className="py-16 text-center">
                    <div className="mx-auto w-fit">
                      <FolderIcon />
                    </div>
                    <p className="mt-3 text-sm text-zinc-400">
                      {activeLib
                        ? "这个库还没有资料，点右上角「上传」或「写笔记」。"
                        : "点下方按钮新建，或在左侧目录树右键新建"}
                    </p>
                    {libraries.length === 0 && (
                      <button
                        type="button"
                        onClick={() => void newLibraryViaPrompt()}
                        className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-teal-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                          <path d="M12 5v14M5 12h14" />
                        </svg>
                        新建第一个知识库
                      </button>
                    )}
                  </div>
                ) : (
                  <ul className="space-y-1">
                    {docs.map((doc) => (
                      <li
                        key={doc.id}
                        onContextMenu={(event) =>
                          openTreeMenu(event, "doc", { doc })
                        }
                      >
                        <button
                          type="button"
                          onClick={() =>
                            router.push(`/knowledge/doc/${doc.id}`)
                          }
                          title={`${doc.title}（右键可删除）`}
                          className="animate-fade-up flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-black/[0.03] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                        >
                          <DocIcon className="shrink-0 text-zinc-400" />
                          <span className="min-w-0 flex-1 truncate text-sm text-zinc-800">
                            {doc.title}
                          </span>
                          <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
                            {formatDay(doc.created_at)} · {doc.chars} 字
                          </span>
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
                            className="shrink-0 text-zinc-300"
                          >
                            <path d="m9 18 6-6-6-6" />
                          </svg>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            }
          </div>
        </div>
      </section>

      {/* 栏三：AI 问答侧栏（桌面，可收起） */}
      {qaOpen && (
        <aside
          className="relative hidden shrink-0 flex-col border-l border-black/[0.06] bg-white xl:flex"
          style={{ width: qaWidth }}
        >
          {/* 拖拽柄：悬停/拖拽时 3px 主题色高亮 */}
          <div
            role="separator"
            aria-orientation="vertical"
            onMouseDown={startQaDrag}
            onDoubleClick={() => setQaWidth(384)}
            title="拖拽调节宽度（双击恢复默认）"
            className="group absolute -left-1 top-0 z-20 h-full w-2 cursor-col-resize"
          >
            <div
              className={`absolute left-1/2 top-0 h-full -translate-x-1/2 transition-all duration-150 ${
                isDragging
                  ? "w-[3px] bg-teal-600"
                  : "w-px bg-black/[0.06] group-hover:w-[3px] group-hover:bg-teal-600"
              }`}
            />
          </div>
          <QaPanel {...qaProps} onClose={() => setQaOpen(false)} />
        </aside>
      )}

      {/* 窄屏：抽屉式问答 */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div
            className="absolute inset-0 bg-black/25 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
            aria-hidden
          />
          <aside className="animate-fade-up absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-black/[0.06] bg-white shadow-2xl">
            <QaPanel {...qaProps} onClose={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      {/* 选中文字 → 向 AI 提问 */}
      {selBtn && (
        <button
          type="button"
          onClick={askAboutSelection}
          className="fixed z-50 rounded-full bg-teal-600 px-3 py-1.5 text-xs font-medium text-white shadow-lg transition hover:bg-teal-700"
          style={{ left: selBtn.x, top: selBtn.y + 8 }}
        >
          向 AI 提问
        </button>
      )}

      {/* 右键菜单：新建知识库 / 删除 */}
      {treeMenu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setTreeMenu(null)}
            onContextMenu={(event) => {
              event.preventDefault();
              setTreeMenu(null);
            }}
            aria-hidden
          />
          <div
            className="animate-pop-in fixed z-50 w-48 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10"
            style={{
              left: Math.min(treeMenu.x, window.innerWidth - 200),
              top: Math.min(treeMenu.y, window.innerHeight - 150),
            }}
          >
            <button
              type="button"
              onClick={() => void newLibraryViaPrompt()}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] font-medium text-teal-700 transition hover:bg-black/[0.04]"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 5v14M5 12h14" />
              </svg>
              新建知识库
            </button>
            {treeMenu.kind === "lib" && treeMenu.libName && (
              <button
                type="button"
                onClick={() => void deleteLibraryViaMenu(treeMenu.libName!)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-red-600 transition hover:bg-red-50"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M3 6h18" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                删除「{treeMenu.libName}」
              </button>
            )}
            {treeMenu.kind === "doc" && treeMenu.doc && (
              <button
                type="button"
                onClick={() => void deleteDocumentViaMenu(treeMenu.doc!)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-red-600 transition hover:bg-red-50"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M3 6h18" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                <span className="min-w-0 flex-1 truncate text-left">
                  删除《{treeMenu.doc.title}》
                </span>
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
