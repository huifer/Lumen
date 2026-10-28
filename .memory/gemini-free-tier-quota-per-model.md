---
name: gemini-free-tier-quota-per-model
description: Gemini 免费档配额按模型计（每模型每天约 20 次 generate_content），429 要换模型而不是重试；理解结果必须落盘缓存
type: gotcha
---

# Gemini 免费档：配额按模型计，429 必须换模型

## Why

2026-10 实测（AI Studio 免费 key，`AQ.` 开头的 key 也是官方的）：

- 错误信息里写得很清楚：
  `Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
   limit: 20, model: gemini-3.6-flash, description: Generate content requests per day limit exceeded on Free Tier`
  → **每个模型每天 20 次**（GenerateRequestsPerDayPerProjectPerModel-FreeTier）。
- **配额是按模型算的，不是按 key/项目算的**：两个 key 共用同一项目配额；但 `gemini-3.5-flash-lite` 在
  `gemini-3.6-flash` 配额用光后**照样能调**。
- embedding 模型配额独立（`gemini-embedding-2` 不受 generate 配额影响）。
- 429 之后提示 `retryDelay: 82274s`（≈22 小时），**重试毫无意义**。
- 并发 + 重试会迅速烧穿配额：我并发 3 路 + 每文件重试 3 次，8 个文件就把 3.6-flash 的 20 次配额打满。

## How to apply

- **理解结果必须落盘缓存**（键用 路径+mtime+大小，**不要把模型名写进键**，否则换模型就全部 miss）。
  命中缓存的重建索引是 0 次 API 调用。
- 429（`RESOURCE_EXHAUSTED` / "429" / "QUOTA"）→ **换模型**继续跑，别重试；只有 SSL/超时/5xx 才重试（≤3 次）。
- 免费档常用可用模型：`gemini-3.6-flash`、`gemini-3.5-flash-lite`、`gemini-3.1-flash-lite`、
  `gemini-3.8-flash`（短期可用）、`gemini-embedding-2` / `gemini-embedding-001`。
- 延迟参考（2026-10 实测）：`gemini-3.6-flash` 约 6~7s/图；`gemini-3.5-flash-lite` 约 5s/图；
  `gemini-3.8-flash` 波动大（20s~120s，偶发 SSL 错误），`gemini-3.6-flash` 更稳。

## Related

- [[gemini-model-names-churn]]
- [[langchain-gemini-image-part-format]]
- [[gdg-dev-lumen-demo]]
