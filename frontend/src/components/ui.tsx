// Apple Music 风格的共享 UI 元素：页面骨架、卡片、表单样式、学科配色。
// 设计基准：浅灰画布 + 白卡片 + 红粉主色（#FA2D48）+ 大标题粗排。

import type { ReactNode } from "react";

export const inputClass =
  "w-full rounded-xl border-0 bg-white px-3.5 py-2.5 text-sm text-zinc-900 ring-1 ring-black/10 outline-none transition placeholder:text-zinc-500 focus:ring-2 focus:ring-accent";

export const selectClass =
  "rounded-xl border-0 bg-white px-3 py-2 text-sm text-zinc-900 ring-1 ring-black/10 outline-none transition focus:ring-2 focus:ring-accent";

export const buttonClass =
  "inline-flex items-center justify-center gap-1.5 rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-40";

export const ghostButtonClass =
  "inline-flex items-center justify-center rounded-full bg-black/[0.06] px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-black/[0.1] active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:outline-none";

/** 统一的键盘焦点样式：给导航、胶囊按钮等非 accent 底色的可点元素复用。 */
export const focusRingClass =
  "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:outline-none";

/** 学科库的固定配色：同一个库每次渲染颜色一致（哈希取色，不用随机数）。 */
const LIBRARY_GRADIENTS = [
  "from-rose-500 to-pink-600",
  "from-sky-500 to-blue-600",
  "from-red-500 to-rose-600",
  "from-emerald-500 to-teal-600",
  "from-amber-500 to-orange-600",
  "from-fuchsia-500 to-pink-600",
  "from-cyan-500 to-sky-600",
  "from-lime-500 to-green-600",
] as const;

export function libraryGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return LIBRARY_GRADIENTS[hash % LIBRARY_GRADIENTS.length];
}

export function Page({
  title,
  subtitle,
  action,
  wide,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="h-full overflow-y-auto bg-[#fbfbfc]">
      <div
        className={`mx-auto space-y-6 px-6 pb-10 pt-7 ${
          wide ? "max-w-5xl" : "max-w-4xl"
        }`}
      >
        <header className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && (
              <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
            )}
          </div>
          {action}
        </header>
        {children}
      </div>
    </div>
  );
}

/** 页面加载中的统一占位（细旋转圈）。 */
export function Loading({ text = "加载中…" }: { text?: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-zinc-500">
      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-accent" />
      {text}
    </p>
  );
}

export function Card({
  title,
  action,
  className,
  children,
}: {
  title?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`rounded-xl bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03),0_2px_8px_rgba(0,0,0,0.04)] ${className ?? ""}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-xs font-medium text-zinc-500">
        {label}
      </span>
      {children}
    </label>
  );
}

export function Notice({
  kind,
  children,
}: {
  kind: "ok" | "error";
  children: ReactNode;
}) {
  const style =
    kind === "ok"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-600/15"
      : "bg-red-50 text-red-700 ring-red-600/15";
  return (
    <p className={`rounded-xl px-4 py-2.5 text-sm ring-1 ${style}`}>
      {children}
    </p>
  );
}
