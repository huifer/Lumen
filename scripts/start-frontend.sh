#!/usr/bin/env bash
# 启动前端 (http://127.0.0.1:3000)
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  echo "→ 安装前端依赖…"
  npm install --no-audit --no-fund
fi

echo "→ 前端启动中: http://127.0.0.1:3000"
exec npm run dev
