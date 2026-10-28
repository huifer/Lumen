---
name: gdg-dev-lumen-demo
description: gdg-dev 仓库 = Lumen 本地多模态文件检索 demo（Next.js 前端 + FastAPI 后端），按用户提供的 Lumen 实操教程 PPT 实现
type: decision
---

# gdg-dev · Lumen demo 架构决策（2026-10-28）

## Why

用户给了一份《Lumen 本地多模态文件检索 · 实操教程》PPT（14 页，流程：采集 → 理解 → 索引 → 检索 → 呈现，
Gemini 在线 + 离线兜底双后端），要求"用 nextjs + python 做一个 demo，不需要功能很复杂"。
`/Users/zhangsan/git_repo/gdg-dev` 原本是空仓库，因此按 PPT 的模块划分从零搭。

## How to apply

- 仓库结构：`backend/`（Python，FastAPI，包名 `lumen`）+ `frontend/`（Next.js 15 App Router）+ 根 README。
- 后端模块一一对应 PPT：`ingest.py`（采集/主色/截图判定）、`understand.py`（Gemini + OfflineUnderstander）、
  `embed.py`（Gemini embedding / 离线 hashing TF-IDF）、`index_store.py`（落盘）、`pipeline.py`（编排+检索重排）、
  `server.py`（HTTP 接口）。没有做 CLI/Gradio（PPT 里的 CLI+Gradio 换成 Next.js 前端）。
- 离线模式必须能跑通：无 GEMINI_API_KEY 时自动降级，靠 Pillow 视觉特征 + tesseract OCR + 文件名启发式。
- 前端通过 `next.config.mjs` 的 rewrites 把 `/api/*` 代理到 `http://127.0.0.1:8000`，避免 CORS 与前端配置。
- 检索 = 语义相似度（cosine）+ 字面关键词加权（`keyword_score`），命中质量靠"标题+描述+标签+OCR+正文"拼成的
  `searchable_text`。
- 跑法：`backend/.venv/bin/python -m uvicorn lumen.server:app --port 8000` + `frontend: npm run dev`。

## Related

- [[python-store-or-falsy-len-trap]]
- [[tesseract-cli-output-suffix-trap]]
- [[next-15-5-4-cve-upgrade]]
