---
name: gemini-model-names-churn
description: Gemini 模型名迭代极快，旧模型（gemini-2.0-flash / text-embedding-004 等）会被 Google 直接下线；不要写死模型名，用 ListModels 自动发现
type: gotcha
---

# Gemini 模型名会过期，千万别写死

## Why

2026-10 实测现状：
- `text-embedding-004`（2024-05 发布）已于 **2026-01-14 停用**。
- `gemini-2.0-flash` / `gemini-2.0-flash-lite` 已于 **2026-06-01 停用**。
- `gemini-1.5-flash`（PPT 教程里用的）早就不在了。
- 当前可用的是 Gemini 3.x 系列：`gemini-3.6-flash` / `gemini-3.8-flash` / `gemini-3.5-flash` 等做生成，
  `gemini-embedding-001`（GA，支持 768/1536/3072 维）或 `gemini-embedding-2-preview` 做向量化。

如果代码里写死旧名字，第一次真正调 API 就会 400 → demo 直接挂。

## How to apply

- 生成/向量模型名**永远不要硬编码**：启动时 `GET https://generativelanguage.googleapis.com/v1beta/models?key=...`，
  按 `supportedGenerationMethods`（generateContent / embedContent）过滤出可用模型，按偏好列表挑。
- 偏好列表放最前面、显式可覆盖（`GEMINI_MODEL=` / `GEMINI_EMBED_MODEL=` 环境变量一旦设置就优先）。
- 调 API 时多套降级策略：结构化输出（responseSchema）失败就退回 prompt 式 JSON；`outputDimensionality`
  失败就去掉；`batchEmbedContents` 失败就改单条 `embedContent`。Gemini 3 是 thinking 模型，生成 JSON 时
  建议带 `thinkingConfig: {thinkingBudget: 0}` 并 `responseMimeType: application/json` 提升稳定性与延迟。
- 图片统一转 JPEG base64 再内联，避免 bmp/tiff 格式不被接受。
- Gemini 后端整体失败时要**优雅降级到离线**（而不是抛错中断），否则 demo 不可用。
- 异常信息里可能含 API Key，对外暴露前用 `redact()` 把 Key 抹掉。

## Related

- [[gdg-dev-lumen-demo]]
- [[tesseract-cli-output-suffix-trap]]
