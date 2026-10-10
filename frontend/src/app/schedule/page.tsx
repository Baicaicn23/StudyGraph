"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  arrangeScheduleTask,
  createScheduleTask,
  deleteScheduleTask,
  scheduleDay,
  scheduleInbox,
  scheduleWeek,
  unarrangeScheduleTask,
  updateScheduleTask,
  type ScheduleDay,
  type ScheduleTask,
  type ScheduleWeekDay,
} from "@/lib/api";
import { Notice, Page } from "@/components/ui";

/* 时间轴固定 06:00–24:00（与后端排期口径一致） */
const DAY_START = 6 * 60;
const DAY_END = 24 * 60;
const HOUR_HEIGHT = 44;
const TIMELINE_HEIGHT = ((DAY_END - DAY_START) / 60) * HOUR_HEIGHT;
const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const DURATIONS = [15, 30, 45, 60, 90];

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function todayKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function shiftDate(date: string, days: number): string {
  const parsed = new Date(`${date}T00:00:00`);
  parsed.setDate(parsed.getDate() + days);
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`;
}

function minutesToLabel(minutes: number | null): string {
  if (minutes === null) return "未安排";
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
}

function labelToMinutes(value: string): number | null {
  const match = value.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  const minutes = Number(match[1]) * 60 + Number(match[2]);
  return minutes >= 0 && minutes < 24 * 60 ? minutes : null;
}

function dateLabel(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);
  return `${parsed.getFullYear()} 年 ${parsed.getMonth() + 1} 月 ${parsed.getDate()} 日`;
}

interface Form {
  id: number | null;
  title: string;
  note: string;
  date: string;
  startMinutes: number | null;
  duration: number;
}

const EMPTY_FORM: Form = {
  id: null,
  title: "",
  note: "",
  date: "",
  startMinutes: null,
  duration: 30,
};

export default function SchedulePage() {
  const [date, setDate] = useState(todayKey());
  const [day, setDay] = useState<ScheduleDay | null>(null);
  const [week, setWeek] = useState<ScheduleWeekDay[]>([]);
  const [inbox, setInbox] = useState<ScheduleTask[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [nowMinutes, setNowMinutes] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [nextDay, nextWeek, nextInbox] = await Promise.all([
        scheduleDay(date),
        scheduleWeek(date),
        scheduleInbox(),
      ]);
      setDay(nextDay);
      setWeek(nextWeek.days);
      setInbox(nextInbox);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [date]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  // 「现在」红线：只在看今天时显示，且定时推进
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setNowMinutes(now.getHours() * 60 + now.getMinutes());
    };
    const timer = window.setInterval(tick, 30_000);
    tick();
    return () => window.clearInterval(timer);
  }, []);

  // 打开页面先把时间轴滚到当前时刻附近
  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const now = new Date();
    const minutes = Math.max(DAY_START, now.getHours() * 60 + now.getMinutes());
    node.scrollTop = ((minutes - DAY_START) / 60) * HOUR_HEIGHT - 120;
  }, []);

  const isToday = date === todayKey();
  const nowTop = useMemo(() => {
    if (!isToday || nowMinutes === null || nowMinutes < DAY_START) return null;
    return ((Math.min(nowMinutes, DAY_END) - DAY_START) / 60) * HOUR_HEIGHT;
  }, [isToday, nowMinutes]);

  const openCreate = (startMinutes: number | null = null) => {
    setError("");
    setForm({ ...EMPTY_FORM, date, startMinutes, duration: 30 });
  };

  const openEdit = (task: ScheduleTask) => {
    setError("");
    setForm({
      id: task.id,
      title: task.title,
      note: task.note,
      date: task.date ?? date,
      startMinutes: task.start_minutes,
      duration: task.duration_minutes,
    });
  };

  const onSubmit = async (target: "timeline" | "inbox") => {
    if (!form) return;
    const title = form.title.trim();
    if (!title) {
      setError("给任务起个名字吧");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (form.id === null) {
        await createScheduleTask({
          title,
          note: form.note,
          duration_minutes: form.duration,
          date: target === "timeline" ? form.date : null,
          start_minutes: target === "timeline" ? form.startMinutes : null,
        });
      } else if (target === "inbox") {
        await unarrangeScheduleTask(form.id);
        await updateScheduleTask(form.id, {
          title,
          note: form.note,
          duration_minutes: form.duration,
        });
      } else {
        await updateScheduleTask(form.id, {
          title,
          note: form.note,
          duration_minutes: form.duration,
          date: form.date,
          start_minutes: form.startMinutes ?? undefined,
        });
      }
      setForm(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onToggleDone = async (task: ScheduleTask) => {
    try {
      await updateScheduleTask(task.id, { done: !task.done });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onArrange = async (task: ScheduleTask) => {
    try {
      await arrangeScheduleTask(task.id, date);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onDelete = async () => {
    if (!form?.id) return;
    if (!window.confirm("确定删除这个任务吗？删除后无法恢复。")) return;
    setBusy(true);
    try {
      await deleteScheduleTask(form.id);
      setForm(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const tasks = day?.tasks ?? [];
  const doneCount = tasks.filter((task) => task.done).length;

  return (
    <Page
      wide
      title="日程"
      subtitle="把想法先丢进收件箱，想好了再排进时间轴。"
    >
      {error && <Notice kind="error">{error}</Notice>}

      {/* 日期头 */}
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <h2 className="text-lg font-bold tracking-tight">
            {dateLabel(date)}
          </h2>
          <span className="text-xs text-zinc-400">
            {WEEKDAYS[new Date(`${date}T00:00:00`).getDay()]}
            {isToday && " · 今天"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setDate((prev) => shiftDate(prev, -1))}
            aria-label="前一天"
            className="grid h-8 w-8 place-items-center rounded-lg border border-black/[0.08] text-zinc-500 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="m15 18-6-6 6-6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => setDate(todayKey())}
            className="rounded-lg border border-black/[0.08] px-3 py-1.5 text-xs text-zinc-600 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
            今天
          </button>
          <button
            type="button"
            onClick={() => setDate((prev) => shiftDate(prev, 1))}
            aria-label="后一天"
            className="grid h-8 w-8 place-items-center rounded-lg border border-black/[0.08] text-zinc-500 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="m9 18 6-6-6-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* 周条：点任一天切换，圆点 = 当天排期密度 */}
      <div className="grid grid-cols-7 gap-1.5">
        {week.map((item) => {
          const parsed = new Date(`${item.date}T00:00:00`);
          const active = item.date === date;
          const isDayToday = item.date === todayKey();
          return (
            <button
              key={item.date}
              type="button"
              onClick={() => setDate(item.date)}
              className={`rounded-xl py-2 transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                active
                  ? "bg-teal-600/[0.08] ring-1 ring-teal-600/40"
                  : "hover:bg-black/[0.04]"
              }`}
            >
              <div
                className={`text-[10px] ${
                  active || isDayToday ? "text-teal-700" : "text-zinc-400"
                }`}
              >
                {WEEKDAYS[parsed.getDay()]}
              </div>
              <div
                className={`mt-0.5 text-sm tabular-nums ${
                  active
                    ? "font-semibold text-teal-800"
                    : isDayToday
                      ? "font-medium text-teal-700"
                      : "text-zinc-600"
                }`}
              >
                {parsed.getDate()}
              </div>
              <div className="mt-1 flex h-1.5 items-center justify-center gap-[3px]">
                {Array.from({ length: Math.min(item.total, 4) }).map((_, index) => (
                  <span
                    key={index}
                    className={`block h-1.5 w-1.5 rounded-full ${
                      index < item.done ? "bg-teal-600" : "bg-teal-200"
                    }`}
                  />
                ))}
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        {/* 收件箱 */}
        <div className="w-full shrink-0 rounded-2xl border border-black/[0.06] bg-zinc-50 p-4 lg:w-[250px]">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-800">收件箱</span>
            <span className="text-[11px] tabular-nums text-zinc-400">
              {inbox.length}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            随手记下的想法，想好了再排进时间轴
          </p>
          <div className="mt-3 space-y-1.5">
            {inbox.map((task) => (
              <div
                key={task.id}
                className="rounded-xl border border-black/[0.06] bg-white px-3 py-2.5"
              >
                <button
                  type="button"
                  onClick={() => openEdit(task)}
                  className="block w-full text-left text-[13px] text-zinc-800 focus-visible:outline-none"
                >
                  <span className="line-clamp-2">{task.title}</span>
                </button>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-[10px] text-zinc-400">
                    {task.duration_minutes} 分钟
                  </span>
                  <button
                    type="button"
                    onClick={() => void onArrange(task)}
                    className="text-[10px] font-medium text-teal-700 transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    安排到{isToday ? "今天" : "这一天"} ›
                  </button>
                </div>
              </div>
            ))}
            {inbox.length === 0 && (
              <p className="rounded-xl bg-white px-3 py-4 text-center text-[11px] text-zinc-400 ring-1 ring-black/[0.04]">
                收件箱是空的
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => openCreate(null)}
            className="mt-3 w-full rounded-xl border border-dashed border-teal-600/50 py-2 text-xs font-medium text-teal-700 transition hover:bg-teal-600/[0.06] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
          >
            ＋ 新收件箱任务
          </button>
        </div>

        {/* 时间轴 */}
        <div className="min-w-0 flex-1 rounded-2xl border border-black/[0.06] bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-800">时间轴</span>
            <span className="text-[11px] tabular-nums text-zinc-400">
              完成 {doneCount} / {tasks.length}
            </span>
          </div>

          <div
            ref={scrollRef}
            className="relative mt-3 max-h-[min(70vh,760px)] overflow-y-auto pr-1"
          >
            <div
              className="relative"
              style={{ height: TIMELINE_HEIGHT, marginLeft: 52 }}
            >
              {/* 小时刻度 */}
              {Array.from({ length: (DAY_END - DAY_START) / 60 }).map((_, index) => {
                const minutes = DAY_START + index * 60;
                return (
                  <div
                    key={minutes}
                    className="absolute left-0 right-0"
                    style={{ top: index * HOUR_HEIGHT }}
                  >
                    <span className="absolute -left-12 top-0 w-10 text-right text-[10px] tabular-nums text-zinc-300">
                      {minutesToLabel(minutes)}
                    </span>
                    <div className="h-px w-full bg-black/[0.04]" />
                  </div>
                );
              })}

              {/* 当前时刻 */}
              {nowTop !== null && (
                <div
                  className="absolute left-0 right-0 z-20 border-t border-dashed border-red-500/70"
                  style={{ top: nowTop }}
                >
                  <span className="absolute -left-12 -top-2 w-10 text-right text-[10px] font-medium tabular-nums text-red-500">
                    {minutesToLabel(nowMinutes ?? 0)}
                  </span>
                </div>
              )}

              {/* 任务卡 */}
              {tasks.map((task) => {
                const start = task.start_minutes ?? DAY_START;
                const top = ((start - DAY_START) / 60) * HOUR_HEIGHT;
                const height = Math.max(
                  (task.duration_minutes / 60) * HOUR_HEIGHT,
                  32,
                );
                const end = start + task.duration_minutes;
                return (
                  <div
                    key={task.id}
                    className={`absolute left-0 right-0 z-10 ${task.done ? "opacity-60" : ""}`}
                    style={{ top, height }}
                  >
                    <div
                      className={`group flex h-full items-start gap-2 overflow-hidden rounded-xl border px-3 py-2 transition ${
                        task.done
                          ? "border-black/[0.06] bg-zinc-50"
                          : "border-black/[0.08] bg-white hover:shadow-[0_2px_10px_rgba(0,0,0,0.06)]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => openEdit(task)}
                        className="min-w-0 flex-1 text-left focus-visible:outline-none"
                      >
                        <div className="text-[10px] tabular-nums text-zinc-400">
                          {minutesToLabel(start)} - {minutesToLabel(end)} ·{" "}
                          {task.duration_minutes} 分钟
                        </div>
                        <div
                          className={`mt-0.5 truncate text-[13px] font-medium ${
                            task.done
                              ? "text-zinc-400 line-through"
                              : "text-zinc-800"
                          }`}
                        >
                          {task.title}
                        </div>
                        {task.note && height > 60 && (
                          <div className="mt-0.5 line-clamp-2 text-[11px] text-zinc-400">
                            {task.note}
                          </div>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => void onToggleDone(task)}
                        aria-label={task.done ? "标记未完成" : "标记完成"}
                        title={task.done ? "标记未完成" : "标记完成"}
                        className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                          task.done
                            ? "border-teal-600 bg-teal-600 text-white"
                            : "border-teal-300 hover:border-teal-600"
                        }`}
                      >
                        {task.done && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}

              {tasks.length === 0 && (
                <div className="absolute inset-x-0 top-16 text-center text-xs text-zinc-400">
                  这一天还没有安排。点右下角 ＋ 新建，或从收件箱安排一条。
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 新建 / 编辑弹窗 */}
      {form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 px-4">
          <div className="animate-pop-in w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold tracking-tight">
                {form.id === null ? "新建任务" : "编辑任务"}
              </h2>
              <button
                type="button"
                onClick={() => setForm(null)}
                aria-label="关闭"
                className="grid h-7 w-7 place-items-center rounded-lg text-zinc-400 transition hover:bg-black/[0.05] hover:text-zinc-700"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <input
              autoFocus
              value={form.title}
              onChange={(event) =>
                setForm((prev) => (prev ? { ...prev, title: event.target.value } : prev))
              }
              maxLength={120}
              placeholder="任务名称，比如：复习特征值"
              className="mt-3 w-full rounded-xl bg-white px-3.5 py-2.5 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:ring-2 focus:ring-teal-600"
            />

            {/* 日期 */}
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {[
                { label: "今天", value: todayKey() },
                { label: "明天", value: shiftDate(todayKey(), 1) },
                { label: "后天", value: shiftDate(todayKey(), 2) },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() =>
                    setForm((prev) => (prev ? { ...prev, date: option.value } : prev))
                  }
                  className={`rounded-full px-3 py-1.5 text-xs transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                    form.date === option.value
                      ? "bg-teal-600/[0.1] font-medium text-teal-800 ring-1 ring-teal-600/40"
                      : "text-zinc-500 hover:bg-black/[0.04]"
                  }`}
                >
                  {option.label}
                </button>
              ))}
              <input
                type="date"
                value={form.date}
                onChange={(event) =>
                  setForm((prev) => (prev ? { ...prev, date: event.target.value } : prev))
                }
                className="rounded-full bg-black/[0.04] px-3 py-1.5 text-xs text-zinc-600 outline-none focus:ring-2 focus:ring-teal-600"
              />
            </div>

            {/* 开始时间 + 时长 */}
            <div className="mt-3 flex gap-3">
              <label className="flex-1 text-[11px] text-zinc-400">
                开始时间
                <input
                  type="time"
                  value={
                    form.startMinutes === null
                      ? ""
                      : minutesToLabel(form.startMinutes)
                  }
                  onChange={(event) =>
                    setForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            startMinutes: labelToMinutes(event.target.value),
                          }
                        : prev,
                    )
                  }
                  className="mt-1.5 block w-full rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-black/10 outline-none focus:ring-2 focus:ring-teal-600"
                />
              </label>
              <div className="flex-1">
                <span className="text-[11px] text-zinc-400">时长</span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {DURATIONS.map((minutes) => (
                    <button
                      key={minutes}
                      type="button"
                      onClick={() =>
                        setForm((prev) =>
                          prev ? { ...prev, duration: minutes } : prev,
                        )
                      }
                      className={`rounded-lg px-2.5 py-1.5 text-[11px] tabular-nums transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                        form.duration === minutes
                          ? "bg-teal-600/[0.1] font-medium text-teal-800 ring-1 ring-teal-600/40"
                          : "text-zinc-500 ring-1 ring-black/[0.08] hover:bg-black/[0.04]"
                      }`}
                    >
                      {minutes} 分
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <textarea
              rows={2}
              value={form.note}
              onChange={(event) =>
                setForm((prev) => (prev ? { ...prev, note: event.target.value } : prev))
              }
              maxLength={2000}
              placeholder="备注（可选）：完成标准、材料在哪…"
              className="mt-3 w-full resize-none rounded-xl bg-zinc-50 px-3.5 py-2.5 text-sm ring-1 ring-black/10 outline-none transition placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-teal-600"
            />

            <div className="mt-4 flex items-center gap-2">
              {form.id !== null && (
                <button
                  type="button"
                  onClick={() => void onDelete()}
                  disabled={busy}
                  className="rounded-full px-3 py-2 text-xs font-medium text-red-600 transition hover:bg-red-50 focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none disabled:opacity-40"
                >
                  删除
                </button>
              )}
              <span className="flex-1" />
              <button
                type="button"
                onClick={() => void onSubmit("inbox")}
                disabled={busy}
                className="rounded-full border border-black/[0.1] px-4 py-2 text-xs font-medium text-zinc-600 transition hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-40"
              >
                先放收件箱
              </button>
              <button
                type="button"
                onClick={() => void onSubmit("timeline")}
                disabled={busy}
                className="rounded-full bg-teal-600 px-4 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-40"
              >
                放进时间轴
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FAB：快捷新建（默认落在当前日期的第一个空档） */}
      <button
        type="button"
        onClick={() => openCreate(null)}
        aria-label="新建任务"
        title="新建任务"
        className="fixed bottom-8 right-8 z-30 grid h-12 w-12 place-items-center rounded-full bg-teal-600 text-white shadow-lg transition hover:bg-teal-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-95"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </Page>
  );
}
