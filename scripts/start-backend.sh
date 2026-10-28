#!/usr/bin/env bash
# 启动后端 API（http://127.0.0.1:8000）
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  echo "→ 创建虚拟环境并安装依赖…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

echo "→ 后端启动中: http://127.0.0.1:8000  (docs: /docs)"
exec .venv/bin/python -m uvicorn lumen.server:app --host 127.0.0.1 --port 8000 --reload
