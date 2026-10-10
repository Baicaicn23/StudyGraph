"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, use, useCallback, useEffect, useRef, useState } from "react";

import {
  deleteDocument,
  getDocument,
  getHealth,
  streamChat,
  updateDocument,
  type KnowledgeDocument,
  type StreamEvent,
} from "@/lib/api";
import Markdown from "@/components/Markdown";
import KnowledgeTree, { notifyKnowledgeChanged } from "@/components/KnowledgeTree";

interface Heading {
  level: number;
  text: string;
  index: number;
}

interface QaMessage {
  role: "user" | "assistant";
  content: string;
}

const QUICK_ASKS = ["总结这篇笔记", "这篇笔记的重点是什么", "出 3 道相关练习题"];
const DOC_QA_WIDTH_KEY = "studygraph-doc-qa-width";

/** 从 Markdown 正文提取标题，生成目录（按出现顺序编号，供滚动定位）。 */
function extractHeadings(content: string): Heading[] {
  const headings: Heading[] = [];
  let inCodeBlock = false;
  content.split("\n").forEach((line) => {
    if (line.trimStart().startsWith("```")) {
      inCodeBlock = !inCodeBlock;
      return;
    }
    if (inCodeBlock) return;
    const match = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (match) {
      headings.push({
        level: match[1].length,
        text: match[2].replace(/[`*_~]/g, ""),
        index: headings.length,
      });
    }
  });
  return headings;
}

export default function DocPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center bg-white">
          <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-200 border-t-teal-600" />
        </div>
      }
    >
      <DocContent params={params} />
    </Suspense>
  );
}

function DocContent({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const docId = Number(id);

  const [doc, setDoc] = useState<KnowledgeDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeHeading, setActiveHeading] = useState(0);

  const [qaMessages, setQaMessages] = useState<QaMessage[]>([]);
  const [qaInput, setQaInput] = useState("");
  const [qaBusy, setQaBusy] = useState(false);
  const [modelLabel, setModelLabel] = useState("");

  // 编辑 / 删除当前笔记
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const startEdit = useCallback(() => {
    if (!doc) return;
    setEditTitle(doc.title);
    setEditContent(doc.content);
    setEditError("");
    setEditing(true);
  }, [doc]);

  const onSaveEdit = useCallback(async () => {
    if (!doc) return;
    if (!editTitle.trim() || !editContent.trim()) {
      setEditError("标题和正文都不能为空");
      return;
    }
    setSaving(true);
    setEditError("");
    try {
      await updateDocument(doc.id, editTitle.trim(), editContent);
      const fresh = await getDocument(doc.id);
      setDoc(fresh);
      setHeadings(extractHeadings(fresh.content));
      setEditing(false);
      notifyKnowledgeChanged();
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }, [doc, editTitle, editContent]);

  const onDeleteDoc = useCallback(async () => {
    if (!doc) return;
    const ok = window.confirm(
      `确定删除笔记《${doc.title}》吗？删除后不可恢复。`,
    );
    if (!ok) return;
    try {
      await deleteDocument(doc.id);
      notifyKnowledgeChanged();
      router.push("/knowledge");
    } catch (err) {
      setEditError((err as Error).message);
    }
  }, [doc, router]);

  // AI 问答栏宽度（可拖拽调节，本地记忆；与知识库页的问答栏互相独立）
  const [qaWidth, setQaWidth] = useState(384);
  const [isDragging, setIsDragging] = useState(false);
  // 右侧边栏：AI 助手 / 文内目录 两个 tab，再点当前 tab 收起整个面板
  const [panelTab, setPanelTab] = useState<"ai" | "outline" | null>("ai");
  const [collapsedHeadings, setCollapsedHeadings] = useState<number[]>([]);

  const contentRef = useRef<HTMLDivElement>(null);
  const qaScrollRef = useRef<HTMLDivElement>(null);
  const qaThreadRef = useRef("");

  useEffect(() => {
    if (!Number.isFinite(docId) || docId < 1) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("无效的笔记地址");
       
      setLoading(false);
      return;
    }
    getDocument(docId)
      .then((data) => {
        setDoc(data);
        setHeadings(extractHeadings(data.content));
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
    getHealth()
      .then((h) => setModelLabel(h.provider === "mock" ? "Mock 模型" : h.provider))
      .catch(() => setModelLabel(""));
    // 恢复上次调整的问答栏宽度
    try {
      const saved = Number(localStorage.getItem(DOC_QA_WIDTH_KEY));
      if (saved >= 320 && saved <= 720) setQaWidth(saved);
    } catch {
      /* ignore */
    }
  }, [docId]);

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
        localStorage.setItem(DOC_QA_WIDTH_KEY, String(latest));
      } catch {
        /* ignore */
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [qaWidth]);

  useEffect(() => {
    qaScrollRef.current?.scrollTo({
      top: qaScrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [qaMessages]);

  /* 滚动监听：高亮当前所在章节 */
  const onContentScroll = useCallback(() => {
    const container = contentRef.current;
    if (!container) return;
    const elements = container.querySelectorAll("h1,h2,h3,h4,h5,h6");
    const containerTop = container.getBoundingClientRect().top;
    let current = 0;
    elements.forEach((el, index) => {
      if (el.getBoundingClientRect().top - containerTop <= 90) {
        current = index;
      }
    });
    setActiveHeading(current);
  }, []);

  const scrollToHeading = (index: number) => {
    const elements = contentRef.current?.querySelectorAll("h1,h2,h3,h4,h5,h6");
    elements?.[index]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  /* ---------- AI 问答（绑定当前库 + 当前笔记） ---------- */
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
      if (!text || qaBusy || !doc) return;
      if (!qaThreadRef.current) {
        qaThreadRef.current = `doc-${doc.id}-${Math.random().toString(36).slice(2, 8)}`;
      }
      setQaInput("");
      setQaBusy(true);
      setQaMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "" },
      ]);
      // 绑定当前笔记：问题前注入笔记上下文，检索范围限定所属学科库
      await streamChat(
        {
          message: `【我正在阅读笔记《${doc.title}》，学科：${doc.library}】${text}`,
          thread_id: qaThreadRef.current,
          knowledge_bases: [doc.library],
        },
        handleQaEvent,
      );
      setQaBusy(false);
    },
    [qaInput, qaBusy, doc, handleQaEvent],
  );

  return (
    <div className="flex h-full bg-white">
      {/* 左栏：知识库文件树（常驻，与列表页同一棵树） */}
      <KnowledgeTree
        activeDocId={Number.isFinite(docId) ? docId : null}
        className="hidden w-60 lg:flex"
      />

      {/* 中栏：笔记正文 */}
      <section className="flex min-w-0 flex-1 flex-col border-r border-black/[0.06]">
        <header className="border-b border-black/[0.06] px-6 pt-4 pb-3">
          <div className="flex items-center justify-between gap-3">
            <nav className="flex min-w-0 items-center gap-1.5 text-xs text-zinc-400">
              <Link href="/knowledge" className="transition hover:text-teal-700">
                知识库
              </Link>
              {doc && (
                <>
                  <span className="text-zinc-300">/</span>
                  <span>{doc.library}</span>
                  <span className="text-zinc-300">/</span>
                  <span className="truncate font-medium text-zinc-600">
                    {doc.title}
                  </span>
                </>
              )}
            </nav>
            {doc && (
              <div className="flex shrink-0 items-center gap-1.5">
                {editing ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="rounded-full bg-black/[0.05] px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-black/[0.09]"
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      onClick={() => void onSaveEdit()}
                      disabled={saving}
                      className="rounded-full bg-teal-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
                    >
                      {saving ? "保存中…" : "保存"}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={startEdit}
                      className="inline-flex items-center gap-1.5 rounded-full bg-black/[0.05] px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-black/[0.09]"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                      </svg>
                      编辑
                    </button>
                    <button
                      type="button"
                      onClick={() => void onDeleteDoc()}
                      title="删除笔记"
                      className="inline-flex items-center gap-1.5 rounded-full bg-black/[0.05] px-3 py-1.5 text-xs font-medium text-zinc-500 transition hover:bg-red-50 hover:text-red-600"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M3 6h18" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                      删除
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </header>

        <div
          ref={contentRef}
          onScroll={onContentScroll}
          className="flex-1 overflow-y-auto px-6 py-6"
        >
          <div className="mx-auto max-w-2xl">
            {loading ? (
              <p className="flex items-center gap-2 text-sm text-zinc-500">
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-teal-600" />
                加载中…
              </p>
            ) : error ? (
              <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-600/10">
                {error}
                <Link
                  href="/knowledge"
                  className="ml-2 font-medium underline underline-offset-2"
                >
                  返回知识库
                </Link>
              </div>
            ) : (
              doc && (
                <article>
                  {editing ? (
                    <div className="space-y-3">
                      {editError && (
                        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-600/10">
                          {editError}
                        </div>
                      )}
                      <input
                        value={editTitle}
                        maxLength={200}
                        onChange={(event) => setEditTitle(event.target.value)}
                        placeholder="标题"
                        className="w-full rounded-xl bg-white px-3.5 py-2.5 text-base font-semibold ring-1 ring-black/10 outline-none transition focus:ring-2 focus:ring-teal-600"
                      />
                      <textarea
                        value={editContent}
                        maxLength={200000}
                        onChange={(event) => setEditContent(event.target.value)}
                        rows={20}
                        placeholder="正文（支持 Markdown）"
                        className="w-full resize-y rounded-xl bg-white px-3.5 py-3 font-mono text-[13px] leading-relaxed ring-1 ring-black/10 outline-none transition focus:ring-2 focus:ring-teal-600"
                      />
                      <p className="text-[11px] text-zinc-400">
                        保存后会自动重建检索索引，AI 问答立刻能看到新内容。
                      </p>
                    </div>
                  ) : (
                    <>
                      <h1 className="text-2xl font-bold tracking-tight">
                        {doc.title}
                      </h1>
                      <p className="mt-1.5 text-[11px] text-zinc-400 tabular-nums">
                        {doc.library} ·{" "}
                        {new Date(doc.created_at * 1000).toLocaleDateString("zh-CN")}{" "}
                        · {doc.content.length} 字
                      </p>
                      <div className="prose prose-zinc mt-5 max-w-none text-sm leading-loose">
                        <Markdown content={doc.content} />
                      </div>
                    </>
                  )}
                </article>
              )
            )}
          </div>
        </div>
      </section>

      {/* 右栏：AI 助手 / 文内目录 双 tab 面板（内联折叠展开，可拖拽调宽） */}
      {panelTab === null && (
        <div className="flex w-11 shrink-0 flex-col items-center gap-2 border-l border-black/[0.06] py-3">
          {(
            [
              { key: "ai", label: "AI 助手", d: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" },
              { key: "outline", label: "目录", d: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              type="button"
              title={`打开${tab.label}`}
              onClick={() => setPanelTab(tab.key)}
              className="grid h-8 w-8 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-teal-700"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d={tab.d} />
              </svg>
            </button>
          ))}
        </div>
      )}

      {panelTab !== null && (
      <aside
        className="relative flex shrink-0 flex-col border-l border-black/[0.06] bg-white"
        style={{ width: qaWidth }}
      >
        {/* 拖拽柄：可拖拽调宽，双击恢复默认 */}
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

        {/* Tab 按钮行：AI 助手 / 目录，再点当前 tab 收起面板 */}
        <div className="flex items-center gap-1 px-3 pt-3 pb-2">
          {(
            [
              { key: "ai" as const, label: "AI 助手", d: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" },
              { key: "outline" as const, label: "目录", d: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" },
            ]
          ).map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setPanelTab((cur) => (cur === tab.key ? null : tab.key))}
              title={panelTab === tab.key ? "收起面板" : `切换到${tab.label}`}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                panelTab === tab.key
                  ? "bg-teal-600/10 text-teal-800 ring-1 ring-teal-600/40"
                  : "text-zinc-500 hover:bg-black/[0.05] hover:text-zinc-700"
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d={tab.d} />
              </svg>
              {tab.label}
            </button>
          ))}
          <span className="flex-1" />
          {panelTab === "outline" && headings.length > 0 && (
            <button
              type="button"
              onClick={() =>
                setCollapsedHeadings((prev) =>
                  prev.length > 0 ? [] : headings.map((h) => h.index),
                )
              }
              className="rounded-lg px-2 py-1 text-[11px] text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700"
            >
              {collapsedHeadings.length > 0 ? "展开全部" : "折叠全部"}
            </button>
          )}
          <button
            type="button"
            onClick={() => setPanelTab(null)}
            title="收起面板"
            className="grid h-7 w-7 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <line x1="15" y1="4" x2="15" y2="20" />
              <rect x="16" y="6" width="4" height="12" rx="1" fill="currentColor" stroke="none" opacity="0.35" />
            </svg>
          </button>
        </div>

        {panelTab === "outline" && (
          <nav className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4">
            {headings.length === 0 ? (
              <p className="px-2 py-2 text-xs text-zinc-400">
                {loading ? "解析中…" : "这篇笔记没有标题结构，无法生成目录。"}
              </p>
            ) : (
              headings.map((heading) => {
                const hasChildren = heading.level <= 2;
                const collapsed = collapsedHeadings.includes(heading.index);
                return (
                  <div
                    key={heading.index}
                    className="relative"
                    style={{ paddingLeft: `${(heading.level - 1) * 0.9}rem` }}
                  >
                    <span
                      className="absolute bottom-1 left-[0.35rem] top-1 w-px bg-black/[0.05]"
                      style={{ left: `${(heading.level - 1) * 0.9 + 0.3}rem` }}
                      aria-hidden
                    />
                    <div className="flex items-center gap-1 rounded-lg pr-1 transition hover:bg-black/[0.03]">
                      {hasChildren ? (
                        <button
                          type="button"
                          onClick={() =>
                            setCollapsedHeadings((prev) =>
                              prev.includes(heading.index)
                                ? prev.filter((i) => i !== heading.index)
                                : [...prev, heading.index],
                            )
                          }
                          title={collapsed ? "展开小节" : "折叠小节"}
                          className="grid h-5 w-5 shrink-0 place-items-center rounded text-zinc-300 transition hover:bg-black/[0.05] hover:text-zinc-600"
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={collapsed ? "" : "rotate-90"}>
                            <path d="m9 18 6-6-6-6" />
                          </svg>
                        </button>
                      ) : (
                        <span className="h-5 w-5 shrink-0" />
                      )}
                      <button
                        type="button"
                        onClick={() => scrollToHeading(heading.index)}
                        title={heading.text}
                        className={`min-w-0 flex-1 truncate py-1.5 text-left text-xs leading-relaxed transition ${
                          activeHeading === heading.index
                            ? "font-medium text-teal-800"
                            : "text-zinc-500 hover:text-zinc-800"
                        }`}
                      >
                        {heading.text}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </nav>
        )}

        {panelTab === "ai" && (
        <div className="-mt-1 px-4 pb-1">
          <p className="truncate text-xs text-zinc-400">
            绑定：{doc ? `《${doc.title}》 · ${doc.library}` : "…"}
            {modelLabel ? ` · ${modelLabel}` : ""}
          </p>
        </div>
        )}

                {panelTab === "ai" && (
        <>
        <div
          ref={qaScrollRef}
          className="flex-1 space-y-4 overflow-y-auto bg-black/[0.02] px-4 py-4"
        >
          {qaMessages.length === 0 ? (
            <div className="mt-14 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-zinc-400 shadow-sm ring-1 ring-black/[0.05]">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
                </svg>
              </div>
              <p className="mt-3 text-sm text-zinc-500">
                针对这篇笔记提问
              </p>
              <div className="mt-4 flex flex-col gap-1.5">
                {QUICK_ASKS.map((text) => (
                  <button
                    key={text}
                    type="button"
                    onClick={() => void sendQa(text)}
                    disabled={!doc || qaBusy}
                    className="mx-auto w-full max-w-[240px] rounded-full bg-white px-3 py-1.5 text-[11px] text-zinc-600 shadow-sm ring-1 ring-black/[0.06] transition hover:text-teal-700 hover:ring-teal-600/40 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40"
                  >
                    {text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            qaMessages.map((msg, index) =>
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
                  </div>
                </div>
              )
            )
          )}
        </div>

        <div className="border-t border-black/[0.06] p-3">
          <textarea
            value={qaInput}
            onChange={(event) => setQaInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendQa();
              }
            }}
            rows={2}
            placeholder="针对这篇笔记提问..."
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
              onClick={() => void sendQa()}
              disabled={qaBusy || !qaInput.trim() || !doc}
              aria-label="发送"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-1 focus-visible:outline-none active:scale-95 disabled:opacity-25"
            >
              {qaBusy ? (
                <span className="block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
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
        )}
      </aside>
      )}
    </div>
  );
}
