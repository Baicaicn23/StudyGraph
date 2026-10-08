"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import {
  listLibraries,
  resumeChat,
  streamChat,
  type Library,
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

const SUGGESTIONS = [
  "帮我算一下 7 * 9",
  "我的笔记里怎么讲导数的？",
  "记住：我在准备月底的微积分测验",
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState<PendingInterrupt | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 会话 id 在浏览器端首次使用时惰性生成（预渲染期不能用随机值）。
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
      // 后端未启动时保持空列表，不影响输入。
    }
  }, []);

  useEffect(() => {
    // 挂载时拉取一次知识库列表（同步外部系统）。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshLibraries();
  }, [refreshLibraries]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

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
      setBusy(false);
    },
    [input, busy, getThreadId, selected, handleEvent, refreshLibraries],
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

  return (
    <div className="flex h-dvh bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 md:flex">
        <div className="mb-6">
          <div className="text-lg font-semibold">StudyGraph</div>
          <div className="text-xs text-zinc-500">个人学习助理 · LangGraph 驱动</div>
        </div>
        <div className="mb-2 text-xs font-medium text-zinc-500">学科知识库</div>
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {libraries.length === 0 ? (
            <p className="text-xs text-zinc-400">
              还没有知识库。在聊天里说「记住：…」沉淀一条笔记试试。
            </p>
          ) : (
            libraries.map((library) => {
              const active = selected.includes(library.name);
              return (
                <button
                  key={library.name}
                  type="button"
                  onClick={() => toggleLibrary(library.name)}
                  className={`flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                    active
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  }`}
                >
                  <span className="truncate">{library.name}</span>
                  <span className="ml-2 text-xs text-zinc-400">
                    {library.document_count}
                  </span>
                </button>
              );
            })
          )}
        </div>
        {selected.length > 0 && (
          <button
            type="button"
            onClick={() => setSelected([])}
            className="mt-3 text-left text-xs text-zinc-500 hover:text-zinc-800"
          >
            清除选择（当前限定 {selected.length} 个库检索）
          </button>
        )}
      </aside>

      <main className="flex flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {messages.length === 0 ? (
              <div className="mt-16 text-center">
                <h1 className="text-2xl font-semibold">你好，我是 StudyGraph</h1>
                <p className="mt-2 text-sm text-zinc-500">
                  算题、讲概念、检索你的资料、把内容沉淀进学科库——都能聊。
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((text) => (
                    <button
                      key={text}
                      type="button"
                      onClick={() => void send(text)}
                      className="rounded-full border border-zinc-300 px-4 py-2 text-sm hover:bg-white dark:border-zinc-700 dark:hover:bg-zinc-900"
                    >
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <MessageBubble key={index} message={message} busy={busy} />
              ))
            )}
          </div>
        </div>

        <div className="border-t border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="输入你的问题，例如：我的笔记里怎么讲导数的？"
              className="max-h-40 flex-1 resize-none rounded-xl border border-zinc-300 bg-zinc-50 px-4 py-3 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950"
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={busy || !input.trim()}
              className="rounded-xl bg-zinc-900 px-5 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {busy ? "……" : "发送"}
            </button>
          </div>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-zinc-400">
            Enter 发送 · Shift+Enter 换行
            {selected.length > 0 ? ` · 检索限定：${selected.join("、")}` : ""}
          </p>
        </div>
      </main>

      {pending && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl dark:bg-zinc-900">
            <h2 className="text-base font-semibold">需要你的确认</h2>
            <p className="mt-1 text-sm text-zinc-500">
              助手想把一条笔记保存到你的知识库：
            </p>
            <div className="mt-3 rounded-xl border border-zinc-200 p-3 text-sm dark:border-zinc-700">
              <div className="font-medium">
                「{pending.library}」 · {pending.title}
              </div>
              <p className="mt-1 line-clamp-4 text-zinc-500">{pending.preview}</p>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => void resolvePending(false)}
                className="rounded-lg border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void resolvePending(true)}
                className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90 dark:bg-zinc-100 dark:text-zinc-900"
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

function MessageBubble({ message, busy }: { message: Message; busy: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl bg-zinc-900 px-4 py-2.5 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold dark:bg-zinc-800">
        SG
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        {message.content ? (
          <Markdown content={message.content} />
        ) : busy ? (
          <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-zinc-400" />
        ) : null}
      </div>
    </div>
  );
}
