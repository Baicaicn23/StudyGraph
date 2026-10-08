"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV = [
  { href: "/", icon: "💬", label: "聊天" },
  { href: "/knowledge", icon: "📚", label: "知识库" },
  { href: "/practice", icon: "✏️", label: "练习复习" },
  { href: "/mistakes", icon: "🔎", label: "错题本" },
  { href: "/plan", icon: "🗓️", label: "今日复习" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex h-dvh bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-6 px-2">
          <div className="text-lg font-semibold">StudyGraph</div>
          <div className="text-xs text-zinc-500">个人学习助理 · LangGraph</div>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                }`}
              >
                <span aria-hidden>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <p className="px-2 text-xs leading-5 text-zinc-400">
          演示账套已预置 5 个学科库；试试问「我的笔记里怎么讲导数的？」。
        </p>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}
