"use client";

import { Check, Plus, X } from "lucide-react";
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

/** 模型选择弹层（胶囊尺度）：思考强度四段 + 模型列表 + 自定义模型。 */
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
    if (
      !form.name.trim() ||
      !form.base_url.trim() ||
      !form.api_key.trim() ||
      !form.model_id.trim()
    ) {
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
    <div className="w-60 rounded-xl border border-black/[0.08] bg-white p-3 shadow-[0_8px_30px_rgba(0,0,0,0.12)]">
      {/* 思考强度：四段紧凑切换 */}
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] font-medium text-zinc-500">思考强度</span>
        <span className="text-[11px] text-teal-700">
          {INTENSITY_LABELS[settings.thinking]}
        </span>
      </div>
      <div className="flex gap-1">
        {INTENSITY_LEVELS.map((level) => {
          const current = settings.thinking === level.value;
          return (
            <button
              key={level.value}
              type="button"
              onClick={() => void onThinkingChange(level.value)}
              className={`flex-1 rounded-md px-1 py-1 text-[11px] transition ${
                current
                  ? "bg-teal-600 font-medium text-white"
                  : "bg-zinc-100 text-zinc-500 hover:bg-teal-600/10 hover:text-teal-700"
              }`}
            >
              {level.label}
            </button>
          );
        })}
      </div>

      <div className="my-2.5 h-px bg-black/[0.06]" />

      {/* 模型列表 */}
      <div className="mb-1 text-[11px] font-medium text-zinc-500">模型</div>
      <ul className="space-y-0.5">
        {settings.models.map((model: ModelOption) => {
          const current = settings.current === model.key;
          return (
            <li key={model.key}>
              <button
                type="button"
                onClick={() => void onModelChange(model.key)}
                className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[11.5px] transition ${
                  current
                    ? "bg-teal-600/10 text-teal-800"
                    : "hover:bg-black/[0.04] text-zinc-700"
                }`}
              >
                <span className="min-w-0 truncate">{model.label}</span>
                <span className="ml-2 flex shrink-0 items-center gap-1 text-[10px] text-zinc-400">
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
                      className="rounded px-0.5 text-zinc-300 transition hover:text-red-400"
                    >
                      <X size={9} />
                    </span>
                  )}
                  {current ? <Check size={10} /> : model.source === "custom" ? "自定义" : ""}
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
          className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-[11px] text-teal-700 transition hover:bg-teal-600/10"
        >
          ＋ 配置自定义模型
        </button>
      ) : (
        <div className="mt-1 space-y-1.5 rounded-lg bg-zinc-50 p-2">
          {(
            [
              ["name", "名称"],
              ["base_url", "接口地址（https://…/v1）"],
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
              className="w-full rounded-md border border-black/[0.08] bg-white px-2 py-1 text-[11px] outline-none focus:border-teal-600"
            />
          ))}
          {formError && (
            <p className="text-[10px] text-red-500">{formError}</p>
          )}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-400">Key 只存本地</span>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => {
                  setFormOpen(false);
                  setFormError("");
                }}
                className="rounded-full px-2 py-0.5 text-[10px] text-zinc-400 hover:text-zinc-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void submitCustom()}
                disabled={saving}
                className="rounded-full bg-teal-600 px-2.5 py-0.5 text-[10px] font-medium text-white transition hover:bg-teal-700 disabled:opacity-40"
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
