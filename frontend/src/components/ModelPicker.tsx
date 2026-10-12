"use client";

import { useState } from "react";

import {
  type ModelOption,
  type ModelSettings,
  type ThinkingIntensity,
} from "@/lib/api";

const INTENSITY_LEVELS: { value: ThinkingIntensity; label: string }[] = [
  { value: "auto", label: "自动" },
  { value: "low", label: "低" },
  { value: "high", label: "高" },
  { value: "max", label: "最大" },
];

const INTENSITY_LABELS: Record<ThinkingIntensity, string> = {
  auto: "自动",
  low: "低",
  high: "高",
  max: "最大",
};

/** 模型选择弹层：思考强度滑杆 + 模型列表 + 自定义模型配置。 */
export function ModelPickerPanel({
  settings,
  onModelChange,
  onThinkingChange,
  onAddCustom,
  onDeleteCustom,
}: {
  settings: ModelSettings;
  onModelChange: (key: string) => Promise<void> | void;
  onThinkingChange: (level: ThinkingIntensity) => Promise<void> | void;
  onAddCustom: (payload: {
    name: string;
    base_url: string;
    api_key: string;
    model_id: string;
  }) => Promise<string | null>;
  onDeleteCustom: (key: string) => Promise<void> | void;
}) {
  const sliderIndex = INTENSITY_LEVELS.findIndex(
    (level) => level.value === settings.thinking,
  );
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    base_url: "",
    api_key: "",
    model_id: "",
  });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const submitCustom = async () => {
    setFormError("");
    if (!form.name.trim() || !form.base_url.trim() || !form.api_key.trim() || !form.model_id.trim()) {
      setFormError("四项均必填");
      return;
    }
    setSaving(true);
    const newKey = await onAddCustom({ ...form });
    setSaving(false);
    if (newKey) {
      setForm({ name: "", base_url: "", api_key: "", model_id: "" });
      setFormOpen(false);
    } else {
      setFormError("保存失败，请检查各项填写");
    }
  };

  return (
    <div className="absolute bottom-full left-0 z-30 mb-2 w-[min(92vw,380px)] rounded-2xl border border-black/[0.08] bg-white p-4 shadow-[0_8px_30px_rgba(0,0,0,0.12)]">
      {/* 思考强度滑杆 */}
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-zinc-800">思考强度</span>
        <span className="text-[11px] tabular-nums text-zinc-400">
          {INTENSITY_LABELS[settings.thinking]}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={3}
        step={1}
        value={sliderIndex < 0 ? 0 : sliderIndex}
        onChange={(event) => {
          const level = INTENSITY_LEVELS[Number(event.target.value)];
          if (level) void onThinkingChange(level.value);
        }}
        aria-label="思考强度"
        className="mt-3 w-full accent-teal-600"
      />
      <div className="flex justify-between text-[11px] text-zinc-400">
        {INTENSITY_LEVELS.map((level) => (
          <span
            key={level.value}
            className={
              settings.thinking === level.value
                ? "font-medium text-teal-700"
                : undefined
            }
          >
            {level.label}
          </span>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">
        只对推理模型生效；「自动」= 按意图分档（讲解/出题深、计算/闲聊浅）
      </p>

      <div className="my-3 h-px bg-black/[0.06]" />

      {/* 模型列表 */}
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-zinc-800">模型</span>
        <span className="text-[11px] text-zinc-400">选定后所有档位都用它</span>
      </div>
      <ul className="max-h-44 space-y-1 overflow-y-auto">
        {settings.models.map((model: ModelOption) => {
          const current = settings.current === model.key;
          return (
            <li key={model.key}>
              <button
                type="button"
                onClick={() => void onModelChange(model.key)}
                className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-[12px] transition ${
                  current
                    ? "bg-teal-600/10 text-teal-800"
                    : "hover:bg-black/[0.04] text-zinc-700"
                }`}
              >
                <span className="min-w-0 truncate">{model.label}</span>
                <span className="ml-2 flex shrink-0 items-center gap-1.5 text-[11px] text-zinc-400">
                  {model.source === "custom" && !current && (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        event.stopPropagation();
                        void onDeleteCustom(model.key);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.stopPropagation();
                          void onDeleteCustom(model.key);
                        }
                      }}
                      title="删除该自定义模型"
                      className="rounded px-1 text-zinc-300 transition hover:text-red-400"
                    >
                      ✕
                    </span>
                  )}
                  {current ? "✓ 当前" : model.source === "custom" ? "自定义" : "内置"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {/* 自定义模型 */}
      {!formOpen ? (
        <button
          type="button"
          onClick={() => setFormOpen(true)}
          className="mt-2 w-full rounded-lg bg-zinc-50 px-2.5 py-2 text-left text-[12px] text-teal-700 transition hover:bg-teal-600/10"
        >
          ＋ 配置自定义模型
        </button>
      ) : (
        <div className="mt-2 space-y-2 rounded-xl bg-zinc-50 p-3">
          {(
            [
              ["name", "名称（显示用）"],
              ["base_url", "接口地址（如 https://api.xxx.com/v1）"],
              ["api_key", "API Key"],
              ["model_id", "模型 ID"],
            ] as const
          ).map(([field, label]) => (
            <input
              key={field}
              value={form[field]}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, [field]: event.target.value }))
              }
              placeholder={label}
              type={field === "api_key" ? "password" : "text"}
              className="w-full rounded-lg border border-black/[0.08] bg-white px-2.5 py-1.5 text-[12px] outline-none focus:border-teal-600"
            />
          ))}
          {formError && (
            <p className="text-[11px] text-red-500">{formError}</p>
          )}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-400">Key 只存本地数据库</span>
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setFormOpen(false);
                  setFormError("");
                }}
                className="rounded-full px-2.5 py-1 text-[11px] text-zinc-400 hover:text-zinc-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void submitCustom()}
                disabled={saving}
                className="rounded-full bg-teal-600 px-3 py-1 text-[11px] font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
              >
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { INTENSITY_LABELS };
