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
  renameChat,
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
export const CHAT_ACTION_EVENT = "sg:chat-action";

export function notifyChatsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(CHATS_CHANGED_EVENT));
  }
}

/** 让聊天页执行动作（新对话 / 打开某会话）——跨页面导航的交接棒 */
export function stashChatAction(
  action:
    | { type: "new-chat"; projectId?: number }
    | { type: "open"; sessionId: number },
) {
  try {
    sessionStorage.setItem("sg-chat-action", JSON.stringify(action));
  } catch {
    /* ignore */
  }
  // 人已在聊天页时 router.push 是空操作、挂载效果不会重跑，
  // 补发一个事件让聊天页立刻消费这条动作
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(CHAT_ACTION_EVENT));
  }
}

export default function ChatsSection({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [projects, setProjects] = useState<ChatProject[]>([]);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const [chatMenuFor, setChatMenuFor] = useState<number | null>(null);
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

  // 极简化：分组默认折叠（记录里 undefined = 折叠），会话全部归属空间分组
  const isGroupCollapsed = (key: string) => collapsed[key] ?? true;

  const toggleGroup = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !isGroupCollapsed(key) }));

  const openSession = (chat: ChatSession) => {
    stashChatAction({ type: "open", sessionId: chat.id });
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

  const handleDeleteChat = async (sessionId: number) => {
    try {
      await deleteChat(sessionId);
      setChatMenuFor(null);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleRenameChat = async (chat: ChatSession) => {
    const title = window.prompt("重命名对话", chat.title || "新对话")?.trim();
    if (!title || title === chat.title) return;
    try {
      await renameChat(chat.id, title);
      setChatMenuFor(null);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleDeleteProject = async (project: ChatProject) => {
    const chatCount = chats.filter(
      (chat) => chat.project_id === project.id,
    ).length;
    const warning = chatCount
      ? `确定删除课程「${project.name}」吗？\n\n其中的 ${chatCount} 条对话及其消息、附件会一起删除，无法恢复。`
      : `确定删除项目「${project.name}」吗？删除后无法恢复。`;
    if (!window.confirm(warning)) {
      return;
    }
    try {
      await deleteProject(project.id);
      setMenuFor(null);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleRenameProject = async (project: ChatProject) => {
    const name = window.prompt("重命名课程", project.name)?.trim();
    if (!name || name === project.name) return;
    try {
      await renameProject(project.id, name);
      await refreshLists();
    } catch {
      /* ignore */
    }
  };

  const handleNewChatInProject = (projectId: number | null) => {
    if (projectId !== null) {
      setCollapsed((prev) => ({ ...prev, [`p${projectId}`]: false }));
    }
    stashChatAction({ type: "new-chat", projectId: projectId ?? undefined });
    router.push("/");
  };

  const renderSession = (chat: ChatSession) => (
    <div
      key={chat.id}
      className="group relative flex items-center rounded-lg transition hover:bg-black/[0.05]"
    >
      <button
        type="button"
        onClick={() => openSession(chat)}
        className="flex min-w-0 flex-1 items-center gap-2 py-2 pl-8 pr-2 text-left focus-visible:outline-none"
      >
                <span
          className="truncate min-w-0 flex-1 text-[13px] text-zinc-700"
          title={chat.title || "新对话"}
        >
          {chat.title || "新对话"}
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-zinc-400 transition group-hover:opacity-0">
          {relativeTime(chat.updated_at)}
        </span>
      </button>

      {/* 悬停操作：⋯ 菜单 + 气泡＋直接新建对话（时间在悬停时让位） */}
      <div className="absolute right-2 flex items-center gap-0.5 opacity-0 transition group-hover:opacity-100">
        <button
          type="button"
          title="对话操作"
          onClick={() => setChatMenuFor((v) => (v === chat.id ? null : chat.id))}
          className="grid h-6 w-6 place-items-center rounded-md text-zinc-400 transition hover:bg-black/[0.06] hover:text-zinc-700"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <circle cx="5" cy="12" r="1.7" />
            <circle cx="12" cy="12" r="1.7" />
            <circle cx="19" cy="12" r="1.7" />
          </svg>
        </button>
        <button
          type="button"
          title="在该课程下新建对话"
          onClick={() => handleNewChatInProject(chat.project_id)}
          className="grid h-6 w-6 place-items-center rounded-md text-zinc-400 transition hover:bg-black/[0.06] hover:text-teal-700"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
            <path d="M12 10v6M9 13h6" />
          </svg>
        </button>
      </div>

      {/* ⋯ 菜单：只留重命名 / 删除（对话天然归属所在项目，不提供跨项目移动）*/}
      {chatMenuFor === chat.id && (
        <>
          <div
            className="fixed inset-0 z-30"
            onClick={() => setChatMenuFor(null)}
            aria-hidden
          />
          <div className="absolute right-2 top-full z-40 mt-1 w-40 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-black/10">
            <button
              type="button"
              onClick={() => void handleRenameChat(chat)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] text-zinc-700 transition hover:bg-black/[0.04]"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0 text-zinc-400">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              </svg>
              重命名
            </button>
            <button
              type="button"
              onClick={() => {
                if (
                  !window.confirm(
                    `确定删除「${chat.title || "新对话"}」吗？删除后不可恢复。`,
                  )
                ) {
                  return;
                }
                void handleDeleteChat(chat.id);
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="shrink-0">
                <path d="M3 6h18" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              删除
            </button>
          </div>
        </>
      )}
    </div>
  );

  const renderProject = (project: ChatProject) => {
    const items = chats.filter((chat) => chat.project_id === project.id);
    const key = `p${project.id}`;
    const isCollapsed = isGroupCollapsed(key);
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
            <span
              className="truncate min-w-0 flex-1 text-[13px] font-medium text-zinc-700"
              title={project.name}
            >
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
              title="课程菜单"
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
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                <path d="M12 10v6M9 13h6" />
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
                    系统兜底空间，不可删除
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleDeleteProject(project)}
                    className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
                  >
                    删除项目
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
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto px-2 pb-4">
        <div className="flex items-center justify-between px-2 pb-1.5 pt-1">
          <span className="text-[11px] text-zinc-400">课程空间</span>
        </div>
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
            还没有课程空间。在聊天页右上角「＋ 新对话」里建一个课程，或点下方「新建课程空间」。
          </p>
        )}

        {/* 新建课程空间 */}
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
              placeholder="课程名称，回车确认"
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
