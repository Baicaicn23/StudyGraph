"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { getHealth } from "@/lib/api";
import ChatsSection from "./ChatsSection";

function NavIcon({ name }: { name: string }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "chat":
      return (
        <svg {...common}>
          <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
        </svg>
      );
    case "practice":
      return (
        <svg {...common}>
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
      );
    case "mistakes":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
      );
    case "plan":
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="17" rx="2" />
          <path d="M8 2v4M16 2v4M3 10h18" />
        </svg>
      );
    case "library":
      return (
        <svg {...common}>
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
        </svg>
      );
    default:
      return null;
  }
}

const NAV_ITEMS = [
  { href: "/", icon: "chat", label: "聊天" },
  { href: "/practice", icon: "practice", label: "练习复习" },
  { href: "/mistakes", icon: "mistakes", label: "错题本" },
  { href: "/plan", icon: "plan", label: "今日复习" },
  { href: "/knowledge", icon: "library", label: "知识库" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  // 动态路由（如 /knowledge/doc/[id]）预渲染时 usePathname 不可用，
  // 用 Suspense 包住整个外壳，让预渲染先出骨架、真实导航在请求时注入。
  return (
    <Suspense fallback={<div className="h-dvh bg-white" />}>
      <AppShellInner>{children}</AppShellInner>
    </Suspense>
  );
}

function AppShellInner({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [provider, setProvider] = useState<string>("");

  useEffect(() => {
    getHealth()
      .then((h) => setProvider(h.provider))
      .catch(() => setProvider(""));
  }, []);

  return (
    <div className="flex h-dvh bg-white text-zinc-900">
      <aside className="flex w-14 shrink-0 flex-col border-r border-black/[0.06] bg-white lg:w-56">
        {/* 品牌区：名称 + 版本 + 模型状态 pill */}
        <div className="flex items-start justify-center gap-2 px-2 pt-5 pb-4 lg:justify-between lg:px-4">
          <div className="hidden lg:block">
            <div className="text-[15px] font-bold leading-tight tracking-tight">
              StudyGraph
            </div>
            <div className="text-[11px] leading-tight text-zinc-400">
              学习助理 · 0.2.0
            </div>
          </div>
          {provider && (
            <span
              title={
                provider === "mock"
                  ? "当前为确定性 Mock 模型，零 API 消耗"
                  : `已接入真实模型（${provider}）`
              }
              className="hidden items-center gap-1 rounded-full border border-black/[0.08] px-2 py-0.5 text-[10px] font-medium text-zinc-500 lg:inline-flex"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  provider === "mock" ? "bg-zinc-300" : "bg-accent"
                }`}
              />
              {provider === "mock" ? "Mock" : "真实模型"}
            </span>
          )}
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-rose-500 to-pink-600 text-[12px] font-bold text-white lg:hidden">
            SG
          </div>
        </div>

        {/* 功能导航（上）：聊天 / 练习 / 错题 / 复习 / 知识库 */}
        <nav className="px-2.5 pb-2 pt-1">
          <div className="flex flex-col gap-0.5">
            {NAV_ITEMS.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={item.label}
                  className={`flex items-center justify-center gap-2.5 rounded-lg px-2.5 py-[6px] text-[13px] transition focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:outline-none lg:justify-start ${
                    active
                      ? "bg-black/[0.06] font-medium text-zinc-900"
                      : "text-zinc-700 hover:bg-black/[0.04]"
                  }`}
                >
                  <span className="text-zinc-500">
                    <NavIcon name={item.icon} />
                  </span>
                  <span className="hidden lg:inline">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </nav>

        {/* 对话 + 项目（下，WorkBuddy 式；窄屏只显示导航） */}
        <div className="hidden min-h-0 min-w-0 flex-1 lg:flex">
          <ChatsSection pathname={pathname} />
        </div>

        <div className="hidden border-t border-black/[0.06] px-4 py-3 lg:block">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-900 text-[11px] font-semibold text-white">
              学
            </div>
            <div className="text-[13px] font-medium text-zinc-700">
              本地学习者
            </div>
          </div>
        </div>
        {/* 窄屏底部占位：保持原图标布局 */}
        <div className="border-t border-black/[0.06] px-4 py-3 lg:hidden">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-900 text-[11px] font-semibold text-white">
            学
          </div>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}
