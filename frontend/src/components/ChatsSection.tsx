"use client";

// 全局侧栏下部的「对话 + 项目」区（WorkBuddy 式）。
// 所有页面都可见：点会话跳回聊天页并打开；在别的页面也能看到最近的对话。
// 数据自己拉取；聊天页新建/改标题等动作通过 window 事件 "sg:chats-changed" 通知刷新。

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createProject,
  deleteChat,
  deleteProject,
  listChats,
  listProjects,
  moveChat,
  renameProject,
  type ChatProject,
  type ChatSession,
} from "@/lib/api";

/** 相对时间：刚刚 / n 分钟前 / n 小时前 / 昨天 / M月D日 */
function relativeTime(timestamp: number): string {
  const diff = Date.now() / 1000 - timestamp;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 172800) return "昨天";
  const date = new Date(timestamp * 1000);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

export const CHATS_CHANGED_EVENT = "sg:chats-changed";

export function notifyChatsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(CHATS_CHANGED_EVENT));
  }
}

/** 让聊天页执行动作（新对话 / 打开某会话）——跨页面导航的交接棒 */
export function stashChatAction(action: { type: "new-chat" } | { type: "open"; sessionId: number }) {
  try {
    sessionStorage.setItem("sg-chat-action", JSON.stringify(action));
  } catch {
    /* ignore */
  }
}

export default function ChatsSection({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [moving, setMoving] = useState<number | null>(null);
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [creatingProject, setCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");

  const reload = useCallback(() => {
    Promise.all([listProjects(), listChats()])
      .then(([nextProjects, nextChats]) => {
        setProjects(nextProjects);
        setChats(nextChats);
      })
      .catch(() => {
        /* 后端未启动时保持空列表 */
      });
  }, []);

  useEffect(() => {
    void reload();
    const onChange = () => void reload();
    window.addEventListener(CHATS_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(CHATS_CHANGED_EVENT, onChange);
  }, [reload]);

  // 路由变化时也刷新一次（从聊天页发完消息回到其他页，标题可能已更新）
  useEffect(() => {
    void reload();
  }, [pathname, reload]);

  const knownProjectIds = new Set(projects.map((project) => project.id));
  const ungrouped = chats.filter(
    (chat) => chat.project_id === null || !knownProjectIds.has(chat.project_id),
  );

  const toggleGroup = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  const openSession = (chat: ChatSession) => {
    stashChatAction({ type: "open", sessionId: chat.id });
    router.push("/");
  };

  const startNewChat = () => {
    stashChatAction({ type: "new-chat" });
    router.push("/");
  };

  const refreshLists = async () => {
    await reload();
    notifyChatsChanged();
  };

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) {
      setCreatingProject(false);
      return;
    }
    try {
      await createProject(name);
      setNewProjectName("");
      setCreatingProject(false);
      await refreshLists();
    } catch {
      /* 重名等错误静默 */
    }
  };

  const handleMove = async (sessionId: number, projectId: number | null) => {
    try {
      await moveChat(sessionId, projectId);
      setMoving(null);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteChat = async (sessionId: number) => {
    try {
      await deleteChat(sessionId);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteProject = async (projectId: number) => {
    try {
      await deleteProject(projectId);
      setMenuFor(null);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleRenameProject = async (project: ChatProject) => {
    const name = window.prompt("重命名项目", project.name)?.trim();
    if (!name || name === project.name) return;
    try {
      await renameProject(project.id, name);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleNewChatInProject = (projectId: number) => {
    setCollapsed((prev) => ({ ...prev, [`p${projectId}`]: false }));
    stashChatAction({ type: "new-chat" });
    router.push("/");
  };

  const renderSession = (chat: ChatSession) => (
    <div
      key={chat.id}
      className="group relative flex items-center rounded-lg transition hover:bg-black/[0.04]"
    >
      <button
        type="button"
        onClick={() => openSession(chat)}
        className="flex min-w-0 flex-1 items-center gap-2 py-2 pl-8 pr-2 text-left focus-visible:outline-none"
      >
        <span className="min-w-0 flex-1 truncate text-[13px] text-zinc-700">
          {chat.title || "新对话"}
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
          {relativeTime(chat.updated_at)}
        </span>
      </button>

      {/* 悬停操作：移动 / 删除 */}
      <div className="absolute right-1.5 flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
        <button
          type="button"
          title="移动到项目"
          onClick={() => setMoving((v) => (v === chat.id ? null : chat.id))}
          className="grid h-6 w-6 place-items-center rounded-md bg-white/90 text-zinc-400 shadow-sm ring-1 ring-black/5 transition hover:text-teal-700"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <button
          type="button"
          title="删除对话"
          onClick={() => void handleDeleteChat(chat.id)}
          className="grid h-6 w-6 place-items-center rounded-md bg-white/90 text-zinc-400 shadow-sm ring-1 ring-black/5 transition hover:text-red-600"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 6h18" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>

      {moving === chat.id && (
        <div className="absolute right-1 top-full z-30 mt-1 w-44 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
          <div className="px-2 py-1 text-[11px] font-medium text-zinc-400">
            移动到…
          </div>
          <button
            type="button"
            onClick={() => void handleMove(chat.id, null)}
            className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
          >
            未分组
          </button>
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => void handleMove(chat.id, project.id)}
              className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
            >
              {project.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  const renderProject = (project: ChatProject) => {
    const items = chats.filter((chat) => chat.project_id === project.id);
    const key = `p${project.id}`;
    const isCollapsed = Boolean(collapsed[key]);
    return (
      <section key={project.id} className="mt-1">
        <div className="group relative flex items-center rounded-lg px-2 py-1.5 transition hover:bg-black/[0.03]">
          <button
            type="button"
            onClick={() => toggleGroup(key)}
            title={isCollapsed ? "展开项目" : "折叠项目"}
            className="flex min-w-0 flex-1 items-center gap-2 text-left focus-visible:outline-none"
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              className={`shrink-0 text-zinc-300 transition-transform ${
                isCollapsed ? "-rotate-90" : ""
              }`}
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
              <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
            </svg>
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-700">
              {project.name}
            </span>
            {isCollapsed && items.length > 0 && (
              <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
                {items.length}
              </span>
            )}
          </button>

          <div className="flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
            <button
              type="button"
              title="项目菜单"
              onClick={() => setMenuFor((v) => (v === project.id ? null : project.id))}
              className="grid h-6 w-6 place-items-center rounded-md text-zinc-400 transition hover:bg-black/[0.06] hover:text-zinc-700"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <circle cx="5" cy="12" r="1.6" />
                <circle cx="12" cy="12" r="1.6" />
                <circle cx="19" cy="12" r="1.6" />
              </svg>
            </button>
            <button
              type="button"
              title="新对话"
              onClick={() => handleNewChatInProject(project.id)}
              className="grid h-6 w-6 place-items-center rounded-md text-zinc-400 transition hover:bg-black/[0.06] hover:text-teal-700"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>

          {menuFor === project.id && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setMenuFor(null)}
                aria-hidden
              />
              <div className="absolute right-1 top-full z-40 mt-1 w-40 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
                <button
                  type="button"
                  onClick={() => {
                    setMenuFor(null);
                    void handleRenameProject(project);
                  }}
                  className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
                >
                  重命名项目
                </button>
                {Boolean(project.is_default) ? (
                  <div className="px-2.5 py-1.5 text-[11px] text-zinc-400">
                    默认对话空间，不可删除
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleDeleteProject(project.id)}
                    className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
                  >
                    删除项目（对话保留）
                  </button>
                )}
              </div>
            </>
          )}
        </div>
        <div className="space-y-0.5">
          {!isCollapsed &&
            (items.length > 0 ? (
              items.map(renderSession)
            ) : (
              <p className="py-1 pl-8 pr-2 text-[11px] text-zinc-400">
                还没有对话，点「+」开始
              </p>
            ))}
        </div>
      </section>
    );
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* 新对话（WorkBuddy「新建任务」式的普通行） */}
      <div className="px-2.5 pb-1">
        <button
          type="button"
          onClick={startNewChat}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] font-medium text-zinc-800 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
        >
          <span className="text-zinc-500">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v8M8 12h8" />
            </svg>
          </span>
          新对话
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {/* 未分组兜底：正常情况下所有会话都在空间里 */}
        {ungrouped.length > 0 && (
          <section className="mt-1">
            <div className="flex items-center rounded-lg px-2 py-1.5">
              <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-zinc-400">
                未分组
              </span>
              <span className="text-[11px] tabular-nums text-zinc-400">
                {ungrouped.length}
              </span>
            </div>
            <div className="space-y-0.5">{ungrouped.map(renderSession)}</div>
          </section>
        )}

        {/* 项目（空间）分组，默认空间排最前（后端已排序） */}
        {projects.map(renderProject)}

        {projects.length === 0 && ungrouped.length === 0 && (
          <p className="px-3 py-2 text-[11px] leading-relaxed text-zinc-400">
            发第一条消息后，对话会自动保存在「默认对话空间」。
          </p>
        )}

        {/* 新建项目 */}
        {creatingProject ? (
          <div className="mt-2 px-1">
            <input
              autoFocus
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleCreateProject();
                if (event.key === "Escape") setCreatingProject(false);
              }}
              onBlur={() => void handleCreateProject()}
              placeholder="项目名称，回车确认"
              className="w-full rounded-lg bg-white px-2.5 py-1.5 text-[13px] ring-1 ring-teal-600 outline-none"
            />
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setCreatingProject(true)}
            className="mt-2 flex w-full items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-zinc-400 transition hover:bg-black/[0.03] hover:text-zinc-600"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
            新建项目
          </button>
        )}
      </div>
    </div>
  );
}
