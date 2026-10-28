#!/usr/bin/env bash
# 一键：生成样本 → 启动后端 → 启动前端
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 "$ROOT/backend/scripts/make_sample_data.py" || true
"$ROOT/scripts/start-backend.sh" &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

sleep 2
"$ROOT/scripts/start-frontend.sh"
