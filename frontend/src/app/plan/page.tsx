"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  listMemories,
  studyActivity,
  studyPlan,
  studySprint,
  usage,
  type ActivityDay,
  type MemoryItem,
  type SprintPlan,
  type StudyPlan,
  type UsageSummary,
} from "@/lib/api";
import { Card, Loading, Notice, Page } from "@/components/ui";

/* ---------- 小组件 ---------- */

/** 环形进度（掌握度 / 预算占比通用）。 */
function Ring({
  pct,
  size = 76,
  stroke = 7,
  color = "#0d9488",
  children,
}: {
  pct: number;
  size?: number;
  stroke?: number;
  color?: string;
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(0,0,0,0.07)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * c} ${c}`}
          className="transition-[stroke-dasharray] duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        {children}
      </div>
    </div>
  );
}

const HEAT_LEVELS = [
  "border border-black/[0.06] bg-transparent",
  "bg-teal-200",
  "bg-teal-500",
  "bg-teal-700",
];

function heatLevel(exercises: number): number {
  if (exercises <= 0) return 0;
  if (exercises <= 2) return 1;
  if (exercises <= 5) return 2;
  return 3;
}

function weekdayOf(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("zh-CN", {
    weekday: "short",
  });
}

function relativeDay(timestamp: number): string {
  const diff = Date.now() / 1000 - timestamp;
  if (diff < 86400) return "今天记录";
  if (diff < 2 * 86400) return "昨天记录";
  return `${Math.floor(diff / 86400)} 天前记录`;
}

function dayLabel(date: string): string {
  const [, month, day] = date.split("-");
  return `${Number(month)}月${Number(day)}日`;
}

/** 学习活跃度热力图：颜色深浅=练习量，角标红点=新增误区。 */
function Heatmap({
  series,
  onPickMistakeDay,
}: {
  series: ActivityDay[];
  onPickMistakeDay: (task: string) => void;
}) {
  const [view, setView] = useState<"7" | "30">("30");
  const [tipIndex, setTipIndex] = useState<number | null>(null);
  const data = view === "7" ? series.slice(-7) : series;
  const hasData = series.some((day) => day.exercises > 0 || day.mistakes > 0);

  // 30 天视图按周一开头的日历矩阵补齐前导空位
  const cells: (ActivityDay | null)[] = [];
  if (view === "30" && data.length > 0) {
    const leading = (new Date(`${data[0].date}T00:00:00`).getDay() + 6) % 7;
    for (let i = 0; i < leading; i += 1) cells.push(null);
  }
  cells.push(...data);
  while (view === "30" && cells.length % 7 !== 0) cells.push(null);

  const totalExercises = series.reduce((sum, d) => sum + d.exercises, 0);
  const totalMistakes = series.reduce((sum, d) => sum + d.mistakes, 0);
  const scrolls = Math.floor(totalExercises / 40);

  // 浮层锚定在方格上：边缘列向内对齐，避免溢出卡片
  const tipAlign = (index: number) => {
    const col = index % 7;
    if (col <= 1) return "left-0";
    if (col >= 5) return "right-0";
    return "left-1/2 -translate-x-1/2";
  };

  return (
    <Card
      title="学习活跃度"
      action={
        <div className="flex items-center gap-1">
          {(["7", "30"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setView(option)}
              className={`rounded-full px-2.5 py-1 text-xs transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                view === option
                  ? "bg-teal-600 font-medium text-white"
                  : "text-zinc-500 hover:text-zinc-800"
              }`}
            >
              {option}天
            </button>
          ))}
        </div>
      }
    >
      <div className="grid w-fit grid-cols-7 gap-1">
        {cells.map((day, index) =>
          day ? (
            <div
              key={day.date}
              className="relative"
              onMouseEnter={() => setTipIndex(index)}
              onMouseLeave={() => setTipIndex(null)}
            >
              <button
                type="button"
                onClick={() => {
                  if (day.mistakes > 0) {
                    onPickMistakeDay(
                      `回看 ${dayLabel(day.date)} 的 ${day.mistakes} 条误区`,
                    );
                  }
                }}
                aria-label={`${dayLabel(day.date)}：${day.exercises} 道练习，${day.mistakes} 条误区`}
                className={`relative block h-7 w-7 rounded-md transition-transform duration-150 hover:scale-110 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                  HEAT_LEVELS[heatLevel(day.exercises)]
                }`}
              >
                {day.mistakes > 0 && (
                  <span className="absolute right-0.5 top-0.5 flex gap-0.5">
                    {Array.from({
                      length: Math.min(day.mistakes, 3),
                    }).map((_, dotIndex) => (
                      <span
                        key={dotIndex}
                        className="block h-1 w-1 rounded-full bg-accent"
                      />
                    ))}
                  </span>
                )}
              </button>
              {/* 浮层锚定在方格上：第一行向下弹，其余向上弹 */}
              {tipIndex === index && (
                <div
                  className={`pointer-events-none absolute z-30 w-max rounded-xl border border-black/10 bg-white px-3 py-2 shadow-md ${
                    view === "7" || (view === "30" && index < 7)
                      ? "top-full left-0 mt-1.5"
                      : `bottom-full mb-1.5 ${tipAlign(index)}`
                  }`}
                >
                  <div className="text-xs font-semibold text-zinc-900">
                    {dayLabel(day.date)} · {weekdayOf(day.date)}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-teal-500" />
                    练习 {day.exercises} 道
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
                    误区 {day.mistakes} 条
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div key={`blank-${index}`} className="h-7 w-7" />
          ),
        )}
      </div>

      {/* 图例：误区说明靠左，色阶渐变条靠右 */}
      <div className="mt-3 flex items-center justify-between text-[11px] text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
          当日新增误区
        </span>
        <span className="flex items-center gap-1.5">
          少
          <span className="h-2 w-28 rounded-full bg-gradient-to-r from-zinc-200 via-teal-300 to-teal-700" />
          多
        </span>
      </div>

      {/* 具象化文案 */}
      <p className="mt-3 text-xs text-zinc-500">
        {hasData ? (
          <>
            近 30 天累计完成{" "}
            <span className="font-medium tabular-nums text-zinc-800">
              {totalExercises}
            </span>{" "}
            道练习
            {totalMistakes > 0 && (
              <>
                {" "}
                · 新增{" "}
                <span className="font-medium tabular-nums text-zinc-800">
                  {totalMistakes}
                </span>{" "}
                条误区
              </>
            )}
            ，约相当于刷完{" "}
            <span className="font-semibold tabular-nums text-teal-700">
              {scrolls > 0 ? scrolls : "不到 1"} 套
            </span>{" "}
            <span className="text-zinc-500">期末真题卷（按每套 40 题估算）</span>
          </>
        ) : (
          <span className="font-medium text-zinc-600">
            近 30 天还没有练习记录，
            <Link
              href="/practice"
              className="text-teal-700 underline-offset-2 hover:underline"
            >
              去练习生成 →
            </Link>
          </span>
        )}
      </p>
    </Card>
  );
}

/* ---------- 页面 ---------- */

interface Task {
  text: string;
  done: boolean;
}

export default function PlanPage() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [tokens, setTokens] = useState<UsageSummary | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [activity, setActivity] = useState<ActivityDay[]>([]);
  const [sprint, setSprint] = useState<SprintPlan | null>(null);
  const [sprintDays, setSprintDays] = useState<"3" | "7" | "14">("7");
  const [error, setError] = useState("");

  const [tasks, setTasks] = useState<Task[]>([]);
  const tasksSeeded = useRef(false);
  const [newTask, setNewTask] = useState("");
  const [memoriesExpanded, setMemoriesExpanded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [nextPlan, nextUsage, nextMemories, nextActivity] =
        await Promise.all([
          studyPlan(),
          usage(1),
          listMemories(),
          studyActivity(30),
        ]);
      setPlan(nextPlan);
      setTokens(nextUsage);
      setMemories(nextMemories);
      setActivity(nextActivity);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  // 冲刺计划：切换周期时重拉（.then 链避免 set-state-in-effect 报错）
  useEffect(() => {
    studySprint(Number(sprintDays))
      .then(setSprint)
      .catch((err: Error) => setError(err.message));
  }, [sprintDays]);

  // 任务列表以服务端建议为种子，只初始化一次
  useEffect(() => {
    if (plan && !tasksSeeded.current) {
      tasksSeeded.current = true;
      setTasks(plan.suggestions.map((text) => ({ text, done: false })));
    }
  }, [plan]);

  const doneCount = tasks.filter((task) => task.done).length;
  const progress = tasks.length > 0 ? (doneCount / tasks.length) * 100 : 0;

  const toggleTask = (text: string) =>
    setTasks((prev) =>
      prev.map((task) =>
        task.text === text ? { ...task, done: !task.done } : task,
      ),
    );

  const addTask = () => {
    const text = newTask.trim();
    if (!text || tasks.some((task) => task.text === text)) return;
    setTasks((prev) => [...prev, { text, done: false }]);
    setNewTask("");
  };

  const addTaskFromHeatmap = useCallback((task: string) => {
    setTasks((prev) =>
      prev.some((item) => item.text === task)
        ? prev
        : [...prev, { text: task, done: false }],
    );
  }, []);

  // 冲刺计划某天的全部任务一键加入今日任务（按文本去重）
  const addTasksFromSprint = useCallback((items: string[]) => {
    setTasks((prev) => {
      const existing = new Set(prev.map((task) => task.text));
      const additions = items
        .filter((text) => !existing.has(text))
        .map((text) => ({ text, done: false }));
      return additions.length > 0 ? [...prev, ...additions] : prev;
    });
  }, []);

  // 近 7 天误区峰值（用于指标卡辅助文字）
  const peakDay = activity
    .filter((day) => day.mistakes > 0)
    .sort((a, b) => b.mistakes - a.mistakes)[0];
  const weak = plan?.weak_libraries ?? [];

  return (
    <Page
      wide
      title="今日复习"
      subtitle="汇总到期题、薄弱学科与近期误区，给出「今天先做什么」。"
    >
      {error && <Notice kind="error">{error}</Notice>}

      {/* 第一行：核心指标卡 */}
      <div className="grid gap-6 sm:grid-cols-3">
        {[
          {
            label: "到期练习",
            value: plan ? plan.due_questions.length : "—",
            href: "/practice",
            sub: "间隔重复自动排期",
          },
          {
            label: "薄弱学科",
            value: plan ? weak.length : "—",
            href: "/practice",
            sub:
              plan && weak.length === 0
                ? "暂无薄弱项"
                : plan && weak.length > 0
                  ? `最低 ${Math.min(...weak.map((w) => w.mastery))}%`
                  : "…",
          },
          {
            label: "近 7 天误区",
            value: plan ? plan.recent_mistakes : "—",
            href: "/mistakes",
            sub:
              plan && plan.recent_mistakes > 0 && peakDay
                ? `峰值：${weekdayOf(peakDay.date)}`
                : "近期没有新增",
          },
        ].map((stat, index) => (
          <div key={stat.label} className="animate-fade-up h-full" style={{ animationDelay: `${index * 70}ms` }}>
            <Link
              href={stat.href}
              className="block h-full rounded-xl bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.05)] transition duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <div className="text-xs font-medium text-zinc-500">
                {stat.label}
              </div>
              <div className="mt-2 text-4xl font-bold tracking-tight tabular-nums">
                {stat.value}
              </div>
              <div className="mt-2 flex items-center gap-1 text-[11px] text-zinc-300">
                {stat.sub === "暂无薄弱项" && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="translate-y-px text-emerald-400">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                )}
                {stat.sub}
              </div>
            </Link>
          </div>
        ))}
      </div>

      {/* 第二块：学习活跃度热力图 */}
      <div className="animate-fade-up" style={{ animationDelay: "140ms" }}>
        <Heatmap series={activity} onPickMistakeDay={addTaskFromHeatmap} />
      </div>

      {/* 考前冲刺：按最薄弱优先把任务排进未来 N 天 */}
      <div className="animate-fade-up" style={{ animationDelay: "175ms" }}>
        <Card
          title="考前冲刺"
          action={
            <div className="flex items-center gap-1">
              {(["3", "7", "14"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setSprintDays(option)}
                  className={`rounded-full px-2.5 py-1 text-xs transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                    sprintDays === option
                      ? "bg-teal-600 font-medium text-white"
                      : "text-zinc-500 hover:text-zinc-800"
                  }`}
                >
                  {option}天
                </button>
              ))}
            </div>
          }
        >
          {!sprint ? (
            <Loading text="正在生成冲刺计划…" />
          ) : sprint.schedule.length === 0 ? (
            <p className="text-sm text-zinc-500">{sprint.hint}</p>
          ) : (
            <>
              <p className="mb-3 text-xs text-zinc-500">
                最薄弱的学科优先
                {sprint.total_due > 0 && (
                  <>
                    ，
                    <span className="font-medium tabular-nums text-zinc-800">
                      {sprint.total_due}
                    </span>{" "}
                    道到期题已排入计划
                  </>
                )}
                。
              </p>
              <ol className="space-y-2.5">
                {sprint.schedule.map((day) => (
                  <li
                    key={day.day}
                    className="rounded-xl bg-black/[0.03] px-3.5 py-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 rounded-full bg-teal-600 px-2 py-0.5 text-[10px] font-medium text-white">
                        第 {day.day} 天
                      </span>
                      <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
                        {dayLabel(day.date)}
                      </span>
                      <span className="min-w-0 truncate text-sm font-medium text-zinc-800">
                        {day.focus}
                      </span>
                      <span className="ml-auto shrink-0 text-[11px] tabular-nums text-zinc-400">
                        掌握度 {day.mastery}%
                      </span>
                    </div>
                    <ul className="mt-1.5 space-y-0.5">
                      {day.tasks.map((task) => (
                        <li
                          key={task}
                          className="flex items-start gap-1.5 text-xs text-zinc-600"
                        >
                          <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-teal-500" />
                          <span className="min-w-0">{task}</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      onClick={() => addTasksFromSprint(day.tasks)}
                      className="mt-2 text-[11px] font-medium text-teal-700 transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                    >
                      把这天的任务加入今日任务 →
                    </button>
                  </li>
                ))}
              </ol>
            </>
          )}
        </Card>
      </div>

      {/* 第三行：今日任务 + 长期记忆 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-up" style={{ animationDelay: "210ms" }}>
          <Card
            title="今日任务"
            action={
              <span className="text-[11px] tabular-nums text-zinc-400">
                {doneCount}/{tasks.length}
              </span>
            }
          >
            {/* 进度条 */}
            <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-black/[0.06]">
              <div
                className="h-full rounded-full bg-teal-600 transition-all duration-500 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
            {tasks.length === 0 ? (
              <Loading text="正在生成任务…" />
            ) : (
              <ul className="space-y-2">
                {tasks.map((task) => (
                  <li key={task.text}>
                    <button
                      type="button"
                      onClick={() => toggleTask(task.text)}
                      className="group flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-black/[0.03] focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                    >
                      <span
                        className={`grid h-[18px] w-[18px] shrink-0 place-items-center rounded-[5px] border transition ${
                          task.done
                            ? "border-teal-600 bg-teal-600 text-white"
                            : "border-black/20 group-hover:border-teal-600"
                        }`}
                        aria-hidden
                      >
                        {task.done && (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        )}
                      </span>
                      <span
                        className={`flex-1 text-sm transition ${
                          task.done
                            ? "text-zinc-400 line-through"
                            : "text-zinc-800"
                        }`}
                      >
                        {task.text}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {tasks.length > 0 && doneCount === tasks.length && (
              <p className="mt-3 text-xs font-medium text-teal-700">
                今日任务已全部完成
              </p>
            )}
            {/* 添加新任务 */}
            <div className="mt-4 flex gap-2">
              <input
                value={newTask}
                onChange={(event) => setNewTask(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") addTask();
                }}
                maxLength={60}
                placeholder="添加新任务…"
                className="min-w-0 flex-1 rounded-full bg-white px-3.5 py-1.5 text-xs ring-1 ring-black/10 outline-none placeholder:text-zinc-400 focus:ring-2 focus:ring-accent"
              />
              <button
                type="button"
                onClick={addTask}
                disabled={!newTask.trim()}
                className="shrink-0 rounded-full bg-teal-600 px-3.5 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-teal-700 active:scale-95 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-40"
              >
                添加
              </button>
            </div>
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "280ms" }}>
          <Card
            title="长期记忆"
            action={
              memories.length > 3 ? (
                <button
                  type="button"
                  onClick={() => setMemoriesExpanded((v) => !v)}
                  className="text-xs font-medium text-teal-700 transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                >
                  {memoriesExpanded ? "收起" : `展开全部（${memories.length}）`}
                </button>
              ) : undefined
            }
          >
            {memories.length === 0 ? (
              <p className="text-sm text-zinc-500">
                还没有。在聊天里说「记住：…」试试。
              </p>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  {(memoriesExpanded ? memories : memories.slice(0, 3)).map(
                    (item) => (
                      <span
                        key={item.content}
                        className="inline-flex max-w-full items-center gap-2 rounded-full bg-black/[0.04] py-1.5 pl-3 pr-3.5 text-xs text-zinc-700"
                      >
                        <span className="h-1 w-1 shrink-0 rounded-full bg-teal-500" />
                        <span className="truncate">{item.content}</span>
                        <span className="shrink-0 rounded-full bg-white/90 px-1.5 py-px text-[10px] leading-4 text-zinc-400">
                          {relativeDay(item.created_at)}
                        </span>
                      </span>
                    ),
                  )}
                </div>
                {!memoriesExpanded && memories.length > 3 && (
                  <p className="mt-2 text-[11px] text-zinc-400">
                    还有 {memories.length - 3} 条没有展示
                  </p>
                )}
              </>
            )}
          </Card>
        </div>
      </div>

      {/* 第四行：学科掌握度 + token 用量 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-up" style={{ animationDelay: "350ms" }}>
          <Card title="学科掌握度">
            {weak.length === 0 ? (
              <div className="py-6 text-center">
                <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-xl bg-black/[0.04] text-zinc-400">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v4l2.5 2.5" />
                  </svg>
                </div>
                <p className="mt-3 text-sm text-zinc-500">
                  完成练习后自动生成掌握度分析
                </p>
                <Link
                  href="/practice"
                  className="mt-2 inline-block text-xs font-medium text-teal-700 hover:brightness-110"
                >
                  去做几道题 →
                </Link>
              </div>
            ) : weak.length === 1 ? (
              <div className="flex flex-col items-center py-2">
                <Ring pct={weak[0].mastery} size={116} stroke={9}>
                  <span className="text-xl font-bold tabular-nums">
                    {weak[0].mastery}%
                  </span>
                </Ring>
                <p className="mt-2 text-sm font-medium text-zinc-700">
                  {weak[0].library}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                {weak.map((item) => (
                  <div
                    key={item.library}
                    className="flex flex-col items-center gap-1.5"
                  >
                    <Ring pct={item.mastery}>
                      <span className="text-sm font-bold tabular-nums">
                        {item.mastery}%
                      </span>
                    </Ring>
                    <span className="w-full truncate text-center text-[11px] text-zinc-500">
                      {item.library}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "420ms" }}>
          <Card title="今日 Token 用量">
            {!tokens ? (
              <Loading />
            ) : (
              <div className="flex items-center gap-5">
                <div className="min-w-0 flex-1">
                  <div className="text-4xl font-bold tracking-tight tabular-nums">
                    {tokens.total_tokens.toLocaleString()}
                  </div>
                  {tokens.by_model.length > 0 && (
                    <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-400">
                      {tokens.by_model.map((item) => (
                        <li key={item.model} className="tabular-nums">
                          {item.model} · {item.calls} 次调用
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* 预算占比环 */}
                {typeof tokens.daily_token_budget === "number" &&
                  tokens.daily_token_budget > 0 && (
                    <Ring
                      pct={
                        (tokens.total_tokens / tokens.daily_token_budget) * 100
                      }
                      size={84}
                      stroke={8}
                    >
                      <span className="text-xs font-semibold tabular-nums text-zinc-700">
                        {Math.min(
                          100,
                          Math.round(
                            (tokens.total_tokens / tokens.daily_token_budget) *
                              100,
                          ),
                        )}
                        %
                      </span>
                    </Ring>
                  )}
              </div>
            )}
            {typeof tokens?.daily_token_budget === "number" &&
              tokens.daily_token_budget > 0 && (
                <p className="mt-1 text-xs text-zinc-400 tabular-nums">
                  占每日预算 {tokens.daily_token_budget.toLocaleString()} tokens
                </p>
              )}

            {/* 近 7 天趋势线 */}
            {tokens?.by_day && tokens.by_day.length > 0 && (
              <div className="mt-4">
                <div className="mb-1 text-[11px] text-zinc-400">
                  近 7 天消耗趋势
                </div>
                <svg
                  viewBox="0 0 280 48"
                  className="h-12 w-full"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="近 7 天 token 消耗趋势"
                >
                  {(() => {
                    const values = tokens.by_day.map((item) => item.total_tokens);
                    const max = Math.max(...values, 1);
                    const stepX = 280 / (values.length - 1 || 1);
                    const points = values
                      .map(
                        (value, index) =>
                          `${index * stepX},${44 - (value / max) * 38}`,
                      )
                      .join(" ");
                    return (
                      <g>
                        <polyline
                          points={points}
                          fill="none"
                          stroke="#0d9488"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        {values.map((value, index) => (
                          <circle
                            key={index}
                            cx={index * stepX}
                            cy={44 - (value / max) * 38}
                            r={index === values.length - 1 ? 3 : 2}
                            fill="#0d9488"
                          />
                        ))}
                      </g>
                    );
                  })()}
                </svg>
                <div className="flex justify-between text-[10px] tabular-nums text-zinc-400">
                  <span>{tokens.by_day[0]?.date.slice(5)}</span>
                  <span>{tokens.by_day[tokens.by_day.length - 1]?.date.slice(5)}</span>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </Page>
  );
}
