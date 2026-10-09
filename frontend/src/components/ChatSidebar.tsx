"use client";

// 会话侧栏：WorkBuddy 式的项目分组对话列表。
// - 新聊天自动保存（后端自动起标题），这里只负责展示与组织；
// - 项目分组：会话可移动到项目里，项目删除后会话回到「未分组」。

import { useEffect, useState } from "react";

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

export default function ChatSidebar({
  activeSessionId,
  activeProjectId,
  onSelectSession,
  onNewChat,
  onSelectProject,
  refreshSignal,
  onChatListChanged,
}: {
  activeSessionId: number | null;
  activeProjectId: number | null;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
  onSelectProject: (projectId: number | null) => void;
  /** 父组件在会话标题更新等事件后 +1，触发这里刷新列表 */
  refreshSignal: number;
  onChatListChanged: () => void;
}) {
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [moving, setMoving] = useState<number | null>(null); // 正在移动的会话 id

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [nextProjects, nextChats] = await Promise.all([
          listProjects(),
          listChats(),
        ]);
        if (!cancelled) {
          setProjects(nextProjects);
          setChats(nextChats);
        }
      } catch {
        /* 后端未启动时保持空列表 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshSignal]);

  const knownProjectIds = new Set(projects.map((project) => project.id));
  // 兜底：挂在不存在项目下的会话按「未分组」展示，避免凭空消失
  const ungrouped = chats.filter(
    (chat) => chat.project_id === null || !knownProjectIds.has(chat.project_id),
  );

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    try {
      await createProject(name);
      setNewProjectName("");
      setCreatingProject(false);
      setProjects(await listProjects());
    } catch {
      /* 重名等错误静默 */
    }
  };

  const handleMove = async (sessionId: number, projectId: number | null) => {
    try {
      await moveChat(sessionId, projectId);
      setMoving(null);
      setChats(await listChats());
      onChatListChanged();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteChat = async (sessionId: number) => {
    try {
      await deleteChat(sessionId);
      setChats(await listChats());
      onChatListChanged();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteProject = async (projectId: number) => {
    try {
      await deleteProject(projectId);
      const [nextProjects, nextChats] = await Promise.all([
        listProjects(),
        listChats(),
      ]);
      setProjects(nextProjects);
      setChats(nextChats);
      onChatListChanged();
    } catch {
      /* ignore */
    }
  };

  const handleRenameProject = async (project: ChatProject) => {
    const name = window.prompt("重命名项目", project.name)?.trim();
    if (!name || name === project.name) return;
    try {
      await renameProject(project.id, name);
      setProjects(await listProjects());
    } catch {
      /* ignore */
    }
  };

  const renderSession = (chat: ChatSession) => (
    <div
      key={chat.id}
      className={`group relative flex items-center rounded-lg transition ${
        chat.id === activeSessionId
          ? "bg-teal-600/[0.09]"
          : "hover:bg-black/[0.04]"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelectSession(chat)}
        className="flex min-w-0 flex-1 flex-col items-start px-3 py-2 text-left focus-visible:outline-none"
      >
        <span
          className={`w-full truncate text-[13px] ${
            chat.id === activeSessionId
              ? "font-medium text-teal-800"
              : "text-zinc-700"
          }`}
        >
          {chat.title || "新对话"}
        </span>
        <span className="text-[11px] text-zinc-400">
          {relativeTime(chat.updated_at)}
        </span>
      </button>

      {/* 悬停操作：移动 / 删除 */}
      <div
        className={`absolute right-1.5 flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100 ${
          moving === chat.id ? "opacity-100" : ""
        }`}
      >
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

      {/* 移动菜单 */}
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

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-black/[0.06] bg-zinc-50/80">
      {/* 新聊天 */}
      <div className="p-3">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-3 py-2 text-[13px] font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 5v14M5 12h14" />
          </svg>
          新对话
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {/* 未分组（全部对话的兜底分组） */}
        {ungrouped.length > 0 && (
          <section className="mt-1">
            <button
              type="button"
              onClick={() => onSelectProject(null)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-left text-[11px] font-medium transition ${
                activeProjectId === null
                  ? "bg-black/[0.05] text-zinc-800"
                  : "text-zinc-400 hover:text-zinc-600"
              }`}
            >
              <span>全部对话</span>
              <span className="tabular-nums">{ungrouped.length}</span>
            </button>
            {activeProjectId === null && (
              <div className="mt-0.5 space-y-0.5">{ungrouped.map(renderSession)}</div>
            )}
          </section>
        )}

        {/* 项目分组 */}
        {projects.map((project) => {
          const items = chats.filter((chat) => chat.project_id === project.id);
          return (
            <section key={project.id} className="mt-3">
              <div
                className={`group/project flex items-center justify-between rounded-lg px-3 py-1.5 transition ${
                  activeProjectId === project.id
                    ? "bg-black/[0.05]"
                    : "hover:bg-black/[0.03]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
                    <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
                  </svg>
                  <span
                    className={`truncate text-[11px] font-medium ${
                      activeProjectId === project.id
                        ? "text-zinc-800"
                        : "text-zinc-500"
                    }`}
                  >
                    {project.name}
                  </span>
                  <span className="text-[11px] tabular-nums text-zinc-400">
                    {items.length}
                  </span>
                </button>
                <div className="flex items-center gap-0.5 opacity-0 transition group-hover/project:opacity-100">
                  <button
                    type="button"
                    title="重命名"
                    onClick={() => void handleRenameProject(project)}
                    className="grid h-5 w-5 place-items-center rounded text-zinc-400 transition hover:text-teal-700"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    title="删除项目（对话保留）"
                    onClick={() => void handleDeleteProject(project.id)}
                    className="grid h-5 w-5 place-items-center rounded text-zinc-400 transition hover:text-red-600"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M3 6h18" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                    </svg>
                  </button>
                </div>
              </div>
              {activeProjectId === project.id && (
                <div className="mt-0.5 space-y-0.5">
                  {items.length > 0 ? (
                    items.map(renderSession)
                  ) : (
                    <p className="px-3 py-1.5 text-[11px] text-zinc-400">
                      还没有对话，发一条消息就会自动保存到这里
                    </p>
                  )}
                </div>
              )}
            </section>
          );
        })}

        {/* 新建项目 */}
        {creatingProject ? (
          <div className="mt-3 px-1">
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
            className="mt-3 flex w-full items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] text-zinc-400 transition hover:bg-black/[0.03] hover:text-zinc-600"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
            新建项目
          </button>
        )}
      </div>
    </aside>
  );
}
