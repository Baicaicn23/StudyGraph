"use client";

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import {
  addNote,
  listLibraries,
  uploadDocument,
  type Library,
} from "@/lib/api";

export default function KnowledgePage() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // 上传表单
  const [uploadLibrary, setUploadLibrary] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // 文本笔记表单
  const [noteLibrary, setNoteLibrary] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");

  const refresh = useCallback(async () => {
    try {
      setLibraries(await listLibraries());
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const onUpload = async () => {
    setError("");
    setMessage("");
    if (!uploadLibrary.trim() || !file) {
      setError("请填写学科名并选择文件（TXT / Markdown / PDF）");
      return;
    }
    try {
      const result = await uploadDocument(uploadLibrary.trim(), file);
      setMessage(`已入库：《${result.title}》（${result.chars} 字）`);
      setFile(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onAddNote = async () => {
    setError("");
    setMessage("");
    if (!noteLibrary.trim() || !noteTitle.trim() || !noteContent.trim()) {
      setError("请填写学科、标题与正文");
      return;
    }
    try {
      await addNote(noteLibrary.trim(), noteTitle.trim(), noteContent.trim());
      setMessage(`已保存笔记《${noteTitle.trim()}》`);
      setNoteTitle("");
      setNoteContent("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Page title="知识库" subtitle="按学科沉淀资料；上传或手写笔记，之后检索、出题都基于它们。">
      <section>
        <h2 className="mb-3 text-sm font-medium text-zinc-500">我的学科库</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {libraries.length === 0 ? (
            <p className="text-sm text-zinc-400">
              还没有知识库。用下方表单上传，或运行 `uv run studygraph-demo --reset` 播种演示数据。
            </p>
          ) : (
            libraries.map((library) => (
              <div
                key={library.name}
                className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="font-medium">{library.name}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  {library.document_count} 份资料
                </div>
              </div>
            ))
          )}
        </div>
      </section>

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

      <Card title="上传文件（TXT / Markdown / PDF）">
        <div className="flex flex-col gap-3">
          <Field label="学科名">
            <input
              value={uploadLibrary}
              onChange={(event) => setUploadLibrary(event.target.value)}
              list="library-options"
              placeholder="例如：高等数学-微积分"
              className={inputClass}
            />
          </Field>
          <input
            type="file"
            accept=".txt,.md,.markdown,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <button type="button" onClick={() => void onUpload()} className={buttonClass}>
            上传入库
          </button>
        </div>
      </Card>

      <Card title="写一条文本笔记">
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="学科名">
              <input
                value={noteLibrary}
                onChange={(event) => setNoteLibrary(event.target.value)}
                list="library-options"
                placeholder="例如：线性代数"
                className={inputClass}
              />
            </Field>
            <Field label="标题">
              <input
                value={noteTitle}
                onChange={(event) => setNoteTitle(event.target.value)}
                placeholder="例如：特征值与特征向量"
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="正文">
            <textarea
              value={noteContent}
              onChange={(event) => setNoteContent(event.target.value)}
              rows={4}
              placeholder="贴上或写下你的笔记内容…"
              className={inputClass}
            />
          </Field>
          <button type="button" onClick={() => void onAddNote()} className={buttonClass}>
            保存笔记
          </button>
        </div>
      </Card>

      <datalist id="library-options">
        {libraries.map((library) => (
          <option key={library.name} value={library.name} />
        ))}
      </datalist>
    </Page>
  );
}

const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950";
const buttonClass =
  "self-start rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90 dark:bg-zinc-100 dark:text-zinc-900";

function Page({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
        </header>
        {children}
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-3 text-sm font-medium">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-zinc-500">{label}</span>
      {children}
    </label>
  );
}
