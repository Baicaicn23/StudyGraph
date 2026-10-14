#!/usr/bin/env bash
# 一键启动 知迹 后端 + 前端（开发模式）。
#
# ⚠️ 注意 provider 的优先级：这里故意把 `ZHIJI_LLM_PROVIDER` 默认设成 mock（零 API 消耗），
# 而 `config.py` 用的是 load_dotenv(override=False) —— **已存在的环境变量不会被 .env 覆盖**。
# 所以即使 .env 里写着 openai，直接跑本脚本仍会是 Mock。要录制/演示真实模型请显式指定：
#     ZHIJI_LLM_PROVIDER=openai ./scripts/dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

export ZHIJI_LLM_PROVIDER="${ZHIJI_LLM_PROVIDER:-mock}"

if [[ "$ZHIJI_LLM_PROVIDER" == "mock" ]]; then
  echo "▶ 模型：Mock（确定性回答，零 API 消耗）"
  echo "  想用 .env 里的真实模型：ZHIJI_LLM_PROVIDER=openai ./scripts/dev.sh"
else
  # ⚠️ 变量名必须用花括号界定：后面紧跟的是**全角**括号（多字节），
  # `$ZHIJI_LLM_PROVIDER（` 会被 bash 按字节误并进变量名 → set -u 下报 unbound variable。
  echo "▶ 模型：${ZHIJI_LLM_PROVIDER}（Key / Base URL 读 .env）"
fi

echo "▶ 后端 http://127.0.0.1:8011"
uv run uvicorn zhiji.interfaces.api:app --port 8011 --reload &
BACKEND=$!

echo "▶ 前端 http://localhost:3000"
(cd frontend && npm run dev) &
FRONTEND=$!

cleanup() {
  kill "$BACKEND" "$FRONTEND" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "打开 http://localhost:3000（Ctrl+C 结束）"
wait
