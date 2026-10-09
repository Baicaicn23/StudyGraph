"use client";

// 会话侧栏：WorkBuddy 式项目分组。
// - 项目是文件夹样式的常驻分组，会话直接列在项目下方（右侧相对时间）；
// - 项目行悬停出「…」菜单（重命名/删除）和「+」（在该项目下新建对话）；
// - 正在生成的会话显示小转圈（替代时间位置）。

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

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </svg>
  );
}

export default function ChatSidebar({
  activeSessionId,
  busy,
  onSelectSession,
  onNewChat,
  onNewChatInProject,
  refreshSignal,
  onChatListChanged,
}: {
  activeSessionId: number | null;
  busy: boolean;
  onSelectSession: (session: ChatSession) => void;
  onNewChat: () => void;
  onNewChatInProject: (projectId: number) => void;
  /** 父组件在会话标题更新等事件后 +1，触发这里刷新列表 */
  refreshSignal: number;
  onChatListChanged: () => void;
}) {
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [newProjectName, setNewProjectName] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [moving, setMoving] = useState<number | null>(null); // 正在移动的会话 id
  const [menuFor, setMenuFor] = useState<number | null>(null); // 打开「…」菜单的项目 id
  // 折叠状态："all" = 全部对话分组，其余为项目 id 字符串
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleGroup = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

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

  const refreshLists = async () => {
    const [nextProjects, nextChats] = await Promise.all([
      listProjects(),
      listChats(),
    ]);
    setProjects(nextProjects);
    setChats(nextChats);
  };

  /** 从「+」新建项目内对话：先展开该分组，再切换新对话上下文 */
  const handleNewChatInProject = (projectId: number) => {
    setCollapsed((prev) => ({ ...prev, [`p${projectId}`]: false }));
    onNewChatInProject(projectId);
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
      onChatListChanged();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteChat = async (sessionId: number) => {
    try {
      await deleteChat(sessionId);
      await refreshLists();
      onChatListChanged();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteProject = async (projectId: number) => {
    try {
      await deleteProject(projectId);
      setMenuFor(null);
      await refreshLists();
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

  /** 会话行：标题左、相对时间右；正在生成的会话时间位显示小转圈 */
  const renderSession = (chat: ChatSession) => {
    const isActive = chat.id === activeSessionId;
    return (
      <div
        key={chat.id}
        className={`group relative flex items-center rounded-lg transition ${
          isActive ? "bg-teal-600/[0.09]" : "hover:bg-black/[0.04]"
        }`}
      >
        <button
          type="button"
          onClick={() => onSelectSession(chat)}
          className="flex min-w-0 flex-1 items-center gap-2 py-2 pl-8 pr-2 text-left focus-visible:outline-none"
        >
          <span
            className={`min-w-0 flex-1 truncate text-[13px] ${
              isActive ? "font-medium text-teal-800" : "text-zinc-700"
            }`}
          >
            {chat.title || "新对话"}
          </span>
          {isActive && busy ? (
            <span className="shrink-0 text-teal-600">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                aria-hidden
                className="animate-spin"
              >
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            </span>
          ) : (
            <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
              {relativeTime(chat.updated_at)}
            </span>
          )}
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
  };

  /** 项目分组：文件夹行（点击折叠/展开；悬停出 … 和 +）+ 会话列表 */
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
            <FolderIcon className="shrink-0 text-zinc-400" />
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

          {/* 项目「…」菜单 */}
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
        {/* 未分组兜底：正常情况下所有会话都归属某个空间，这里只在异常数据时出现 */}
        {ungrouped.length > 0 && (
          <section className="mt-1">
            <div className="flex items-center rounded-lg px-2 py-1.5">
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-500">
                未分组
              </span>
              <span className="text-[11px] tabular-nums text-zinc-400">
                {ungrouped.length}
              </span>
            </div>
            <div className="space-y-0.5">{ungrouped.map(renderSession)}</div>
          </section>
        )}

        {/* 项目（空间）分组，默认空间排在最前（后端已排序） */}
        {projects.map(renderProject)}

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
    </aside>
  );
}
