#!/usr/bin/env bash
# 一键启动 StudyGraph 后端 + 前端（开发模式）。默认 Mock 模型，零 API 消耗。
set -euo pipefail
cd "$(dirname "$0")/.."

export STUDYGRAPH_LLM_PROVIDER="${STUDYGRAPH_LLM_PROVIDER:-mock}"

echo "▶ 后端 http://127.0.0.1:8011"
uv run uvicorn studygraph.interfaces.api:app --port 8011 --reload &
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
