"use client";

// 知识库文件树（共享组件）：知识库列表页与笔记详情页共用。
// 自包含：自己拉取数据、管理搜索/展开状态和右键菜单；
// 数据变化通过 window 事件 "sg:knowledge-changed" 通知所有实例刷新。

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createLibrary,
  deleteDocument,
  deleteLibrary,
  listDocuments,
  listLibraries,
  type DocumentItem,
  type Library,
} from "@/lib/api";

export const KNOWLEDGE_CHANGED_EVENT = "sg:knowledge-changed";

export function notifyKnowledgeChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(KNOWLEDGE_CHANGED_EVENT));
  }
}

interface TreeMenu {
  x: number;
  y: number;
  kind: "lib" | "doc" | "blank";
  libName?: string;
  doc?: DocumentItem;
}

interface KnowledgeTreeProps {
  /** 当前打开的笔记 id（详情页传，用于高亮与自动展开所在库） */
  activeDocId?: number | null;
  /** 列表页受控：内容区当前展示的库 */
  activeLib?: string;
  /** 列表页用：点库名切换内容区（不传则点库名只做展开/折叠） */
  onSelectLib?: (name: string) => void;
  /** 树内新建/删除后通知页面刷新自己的数据 */
  onChanged?: () => void;
  className?: string;
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={`shrink-0 text-zinc-300 transition-transform ${
        open ? "rotate-90" : ""
      }`}
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function DocGlyph() {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className="shrink-0 text-zinc-300"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

export default function KnowledgeTree({
  activeDocId = null,
  activeLib,
  onSelectLib,
  onChanged,
  className = "",
}: KnowledgeTreeProps) {
  const router = useRouter();
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [libDocs, setLibDocs] = useState<Record<string, DocumentItem[]>>({});
  const [treeSearch, setTreeSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [menu, setMenu] = useState<TreeMenu | null>(null);

  const refresh = useCallback(() => {
    listLibraries()
      .then((bases) => {
        setLibraries(bases);
        return Promise.all(
          bases.map(
            async (base) =>
              [base.name, await listDocuments(base.name).catch(() => [])] as const,
          ),
        );
      })
      .then((entries) => setLibDocs(Object.fromEntries(entries)))
      .catch(() => {
        /* 后端未启动时保持空树 */
      });
  }, []);

  useEffect(() => {
    void refresh();
    const onChange = () => void refresh();
    window.addEventListener(KNOWLEDGE_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(KNOWLEDGE_CHANGED_EVENT, onChange);
  }, [refresh]);

  // 当前笔记所在库自动展开（渲染期推导，不用 effect）
  const activeDocLib =
    activeDocId != null
      ? Object.entries(libDocs).find(([, docs]) =>
          docs.some((doc) => doc.id === activeDocId),
        )?.[0]
      : undefined;

  const filteredLibs = treeSearch.trim()
    ? libraries.filter((library) =>
        library.name.toLowerCase().includes(treeSearch.trim().toLowerCase()),
      )
    : libraries;

  const handleLibClick = (name: string) => {
    if (onSelectLib) {
      onSelectLib(name); // 列表页：切内容区
      setExpanded((prev) => ({ ...prev, [name]: true }));
    } else {
      setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    }
  };

  const openMenu = (
    event: React.MouseEvent,
    kind: TreeMenu["kind"],
    data?: { libName?: string; doc?: DocumentItem },
  ) => {
    event.preventDefault();
    event.stopPropagation();
    setMenu({ x: event.clientX, y: event.clientY, kind, ...data });
  };

  const createLib = useCallback(async () => {
    setMenu(null);
    const name = window
      .prompt("新建知识库：请输入名称（例如：高等数学）")
      ?.trim();
    if (!name) return;
    try {
      await createLibrary(name);
      setExpanded((prev) => ({ ...prev, [name]: true }));
      notifyKnowledgeChanged();
      onChanged?.();
    } catch (error) {
      window.alert((error as Error).message);
    }
  }, [onChanged]);

  const deleteLib = useCallback(
    async (name: string) => {
      setMenu(null);
      const count = (libDocs[name] ?? []).length;
      const ok = window.confirm(
        `确定删除知识库「${name}」吗？${
          count > 0 ? `其中 ${count} 份资料会一起删除，` : ""
        }此操作不可恢复。`,
      );
      if (!ok) return;
      try {
        await deleteLibrary(name);
        notifyKnowledgeChanged();
        onChanged?.();
      } catch (error) {
        window.alert((error as Error).message);
      }
    },
    [libDocs, onChanged],
  );

  const deleteDoc = useCallback(
    async (doc: DocumentItem) => {
      setMenu(null);
      const ok = window.confirm(`确定删除资料《${doc.title}》吗？不可恢复。`);
      if (!ok) return;
      try {
        await deleteDocument(doc.id);
        // 删掉的正是当前打开的笔记 → 回列表页
        if (doc.id === activeDocId) router.push("/knowledge");
        notifyKnowledgeChanged();
        onChanged?.();
      } catch (error) {
        window.alert((error as Error).message);
      }
    },
    [activeDocId, router, onChanged],
  );

  return (
    <aside
      className={`flex shrink-0 flex-col border-r border-black/[0.06] bg-white ${className}`}
    >
      <div className="px-3 pt-4 pb-2">
        <input
          value={treeSearch}
          onChange={(event) => setTreeSearch(event.target.value)}
          placeholder="搜索资料…"
          className="w-full rounded-xl bg-black/[0.03] px-3 py-1.5 text-xs outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
        />
      </div>
      <div
        className="flex-1 overflow-y-auto overflow-x-hidden px-2 pb-4"
        onContextMenu={(event) => openMenu(event, "blank")}
      >
        {filteredLibs.map((library) => {
          const libOpen =
            Boolean(expanded[library.name]) ||
            activeLib === library.name ||
            activeDocLib === library.name;
          const docs = treeSearch.trim()
            ? (libDocs[library.name] ?? []).filter((doc) =>
                doc.title
                  .toLowerCase()
                  .includes(treeSearch.trim().toLowerCase()),
              )
            : libDocs[library.name] ?? [];
          return (
            <div
              key={library.name}
              className="mb-0.5"
              onContextMenu={(event) =>
                openMenu(event, "lib", { libName: library.name })
              }
            >
              <button
                type="button"
                onClick={() => handleLibClick(library.name)}
                title={library.name}
                className="flex w-full items-center gap-1.5 rounded-lg px-1.5 py-1.5 text-left text-[13px] text-zinc-800 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                <Chevron open={libOpen} />
                <span
                  className={`min-w-0 flex-1 truncate ${
                    activeLib === library.name ? "font-medium" : ""
                  }`}
                >
                  {library.name}
                </span>
                <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
                  {library.document_count}
                </span>
              </button>
              {libOpen &&
                docs.map((doc) => (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => router.push(`/knowledge/doc/${doc.id}`)}
                    onContextMenu={(event) => openMenu(event, "doc", { doc })}
                    title={`${doc.title}（右键可删除）`}
                    className={`relative ml-4 flex w-[calc(100%-1rem)] items-center gap-1.5 rounded-lg py-1.5 pl-2.5 pr-2 text-left text-xs transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                      doc.id === activeDocId
                        ? "bg-teal-600/10 font-medium text-teal-800"
                        : "text-zinc-500 hover:text-zinc-800"
                    }`}
                  >
                    <span
                      className="absolute bottom-1 left-0 top-1 w-px bg-black/[0.06]"
                      aria-hidden
                    />
                    <DocGlyph />
                    <span className="min-w-0 flex-1 truncate">{doc.title}</span>
                  </button>
                ))}
            </div>
          );
        })}
        {libraries.length === 0 && (
          <p className="px-2.5 py-2 text-xs text-zinc-400">
            还没有学科库。右键这里新建。
          </p>
        )}
      </div>

      {/* 右键菜单 */}
      {menu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMenu(null)}
            onContextMenu={(event) => {
              event.preventDefault();
              setMenu(null);
            }}
            aria-hidden
          />
          <div
            className="fixed z-50 w-40 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10"
            style={{
              left: Math.min(menu.x, window.innerWidth - 176),
              top: Math.min(menu.y, window.innerHeight - 140),
            }}
          >
            {menu.kind === "blank" && (
              <button
                type="button"
                onClick={() => void createLib()}
                className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
              >
                新建知识库
              </button>
            )}
            {menu.kind === "lib" && (
              <>
                <button
                  type="button"
                  onClick={() => void createLib()}
                  className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                >
                  新建知识库
                </button>
                <button
                  type="button"
                  onClick={() => void deleteLib(menu.libName!)}
                  className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
                >
                  删除「{menu.libName}」
                </button>
              </>
            )}
            {menu.kind === "doc" && (
              <button
                type="button"
                onClick={() => void deleteDoc(menu.doc!)}
                className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
              >
                删除《{menu.doc!.title.slice(0, 12)}》
              </button>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
