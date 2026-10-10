"use client";

// 日程弹窗里的两个自绘选择器（弃用系统原生控件，配色与全站一致）：
// - TimePicker：等宽数字触发框 + 双列（时/分，5 分钟一档）下拉，「现在」与常用时段快捷键
// - DatePicker：迷你日历下拉（周日开头、可翻月、今天描边、选中实心）

import { useEffect, useRef, useState } from "react";

const HOURS = Array.from({ length: 18 }, (_, index) => index + 6); // 06–23
const MINUTES = Array.from({ length: 12 }, (_, index) => index * 5); // 00–55
const PRESETS = [
  { label: "上午 09:00", minutes: 9 * 60 },
  { label: "晚上 19:00", minutes: 19 * 60 },
  { label: "睡前 22:00", minutes: 22 * 60 },
];
const MONTH_LABELS = [
  "1 月",
  "2 月",
  "3 月",
  "4 月",
  "5 月",
  "6 月",
  "7 月",
  "8 月",
  "9 月",
  "10 月",
  "11 月",
  "12 月",
];
const WEEK_HEADS = ["日", "一", "二", "三", "四", "五", "六"];

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function formatMinutes(minutes: number): string {
  return `${pad(Math.floor(minutes / 60))} : ${pad(minutes % 60)}`;
}

function nowRounded(): number {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  return Math.min(23 * 60 + 55, Math.round(minutes / 5) * 5);
}

function todayKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function dateKey(year: number, month: number, day: number): string {
  return `${year}-${pad(month + 1)}-${pad(day)}`;
}

/* ---------------- 时间选择器 ---------------- */

export function TimePicker({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (minutes: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const nowMinutes = nowRounded();

  // 打开时把选中项滚到中间，省得用户自己找
  useEffect(() => {
    if (open) selectedRef.current?.scrollIntoView({ block: "center" });
  }, [open]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        className={`flex w-full items-center justify-between rounded-xl bg-white px-3 py-2 text-sm ring-1 transition focus-visible:outline-none ${
          open
            ? "ring-2 ring-teal-600"
            : "ring-black/10 hover:ring-black/20 focus-visible:ring-2 focus-visible:ring-teal-600"
        }`}
      >
        <span
          className={`tabular-nums ${
            value === null ? "text-zinc-400" : "text-zinc-900"
          }`}
        >
          {value === null ? "自动安排" : formatMinutes(value)}
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke={open ? "#0f766e" : "#a1a1aa"}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3.5 2" />
        </svg>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="animate-pop-in absolute left-0 top-full z-50 mt-2 w-[228px] rounded-2xl bg-white p-3 shadow-xl ring-1 ring-black/10">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-400">选择时间</span>
              <button
                type="button"
                onClick={() => {
                  onChange(nowMinutes);
                  setOpen(false);
                }}
                className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-0.5 text-[11px] text-teal-700 transition hover:bg-teal-100 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                现在 {formatMinutes(nowMinutes).replace(" : ", ":")}
              </button>
            </div>

            <div className="mt-2.5 flex gap-2">
              <div className="max-h-40 flex-1 overflow-y-auto border-r border-black/[0.06] pr-2">
                <div className="mb-1 text-center text-[10px] text-zinc-400">
                  时
                </div>
                {HOURS.map((hour) => {
                  const minutes = hour * 60;
                  const active = value !== null && Math.floor(value / 60) === hour;
                  return (
                    <button
                      key={hour}
                      ref={active ? selectedRef : undefined}
                      type="button"
                      onClick={() => onChange(minutes + (value === null ? 0 : value % 60))}
                      className={`block w-full rounded-lg py-1.5 text-center text-[13px] tabular-nums transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                        active
                          ? "bg-teal-600/10 font-medium text-teal-800"
                          : "text-zinc-500 hover:bg-black/[0.04]"
                      }`}
                    >
                      {pad(hour)}
                    </button>
                  );
                })}
              </div>
              <div className="max-h-40 flex-1 overflow-y-auto">
                <div className="mb-1 text-center text-[10px] text-zinc-400">
                  分
                </div>
                {MINUTES.map((minute) => {
                  const active = value !== null && value % 60 === minute;
                  return (
                    <button
                      key={minute}
                      ref={active ? selectedRef : undefined}
                      type="button"
                      onClick={() =>
                        onChange(
                          (value === null ? 22 : Math.floor(value / 60)) * 60 + minute,
                        )
                      }
                      className={`block w-full rounded-lg py-1.5 text-center text-[13px] tabular-nums transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                        active
                          ? "bg-teal-600/10 font-medium text-teal-800"
                          : "text-zinc-500 hover:bg-black/[0.04]"
                      }`}
                    >
                      {pad(minute)}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-black/[0.06] pt-2.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    onChange(preset.minutes);
                    setOpen(false);
                  }}
                  className="rounded-full border border-black/[0.08] px-2.5 py-1 text-[11px] text-zinc-600 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ---------------- 日期选择器（迷你日历） ---------------- */

export function DatePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (date: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = new Date(`${value}T00:00:00`);
  // 翻月用显式记录；为 null 时跟随所选日期（打开即是该月，不用 effect 同步）
  const [view, setView] = useState<{ year: number; month: number } | null>(null);
  const today = todayKey();

  const viewYear = view ? view.year : selected.getFullYear();
  const viewMonth = view ? view.month : selected.getMonth();

  const firstDay = new Date(viewYear, viewMonth, 1);
  const leading = firstDay.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  const shiftMonth = (delta: number) => {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setView({ year: next.getFullYear(), month: next.getMonth() });
  };

  const shortLabel = `${selected.getMonth() + 1}月${selected.getDate()}日`;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setView(null); // 每次打开都回到所选日期所在月份
          setOpen((prev) => !prev);
        }}
        aria-expanded={open}
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition focus-visible:outline-none ${
          open
            ? "bg-teal-600/10 font-medium text-teal-800 ring-1 ring-teal-600/40"
            : "text-zinc-500 hover:bg-black/[0.04]"
        }`}
      >
        {shortLabel}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M8 3v4M16 3v4M3 11h18" />
        </svg>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="animate-pop-in absolute left-0 top-full z-50 mt-2 w-[248px] rounded-2xl bg-white p-3 shadow-xl ring-1 ring-black/10">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => shiftMonth(-1)}
                aria-label="上个月"
                className="grid h-6 w-6 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" stroke-linejoin="round" aria-hidden>
                  <path d="m15 18-6-6 6-6" />
                </svg>
              </button>
              <span className="text-xs font-medium text-zinc-700 tabular-nums">
                {viewYear} 年 {MONTH_LABELS[viewMonth]}
              </span>
              <button
                type="button"
                onClick={() => shiftMonth(1)}
                aria-label="下个月"
                className="grid h-6 w-6 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="m9 18 6-6-6-6" />
                </svg>
              </button>
            </div>

            <div className="mt-2 grid grid-cols-7 gap-y-1 text-center">
              {WEEK_HEADS.map((head) => (
                <span key={head} className="text-[10px] text-zinc-400">
                  {head}
                </span>
              ))}
              {cells.map((day, index) => {
                if (day === null) {
                  return <span key={`blank-${index}`} />;
                }
                const key = dateKey(viewYear, viewMonth, day);
                const isSelected = key === value;
                const isToday = key === today;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      onChange(key);
                      setOpen(false);
                    }}
                    className={`mx-auto grid h-7 w-7 place-items-center rounded-full text-[12px] tabular-nums transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                      isSelected
                        ? "bg-teal-600 font-medium text-white"
                        : isToday
                          ? "font-medium text-teal-700 ring-1 ring-teal-600/40"
                          : "text-zinc-600 hover:bg-black/[0.05]"
                    }`}
                  >
                    {day}
                  </button>
                );
              })}
            </div>

            <div className="mt-2 border-t border-black/[0.06] pt-2">
              <button
                type="button"
                onClick={() => {
                  onChange(today);
                  setOpen(false);
                }}
                className="w-full rounded-lg py-1.5 text-center text-[11px] font-medium text-teal-700 transition hover:bg-teal-600/[0.06] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
              >
                回到今天
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
