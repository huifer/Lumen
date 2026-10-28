# Lumen · 本地多模态文件检索（Next.js + Python demo）

用自然语言搜出本地的图片与文档。照着《Lumen 本地多模态文件检索 · 实操教程》的五段式流程实现：
**采集 → 理解 → 索引 → 检索 → 呈现**。

- **后端**：Python + FastAPI（`backend/`）→ 扫描目录、视觉/文本理解、向量化、落盘、检索
- **AI**：**LangChain + Google GenAI**（`langchain-google-genai`）直连 Gemini
  - 理解：`ChatGoogleGenerativeAI` + `with_structured_output`（图片→描述/标签/OCR，文档→摘要/关键词）
  - 向量：`GoogleGenerativeAIEmbeddings`（`gemini-embedding-2`，1536 维）
- **前端**：Next.js 15 App Router（`frontend/`）→ 搜索框 + 结果卡片（缩略图 / 描述 / 标签 / 相似度）
- **不联网也能跑**：没有 `GEMINI_API_KEY` 时自动切离线模式（Pillow 视觉特征 + tesseract OCR）

## 📖 文档

| 文档 | 适合谁 |
| --- | --- |
| [操作手册（小白版）](docs/操作手册.md) | 只想把系统跑起来用一用：装软件、配 Key、启动、搜索、常见问题排查 |
| [开发手册](docs/开发手册.md) | 想读懂/改造这份代码：架构、数据流、API 参考、每个文件职责、二次开发指引 |

## License

[MIT](LICENSE) © 2026 huifer

## 快速开始

```bash
# 1) 后端（首次自动建 venv 装依赖）
./scripts/start-backend.sh          # http://127.0.0.1:8000  (API 文档 /docs)

# 2) 前端
./scripts/start-frontend.sh         # http://127.0.0.1:3000
```

或者一条命令：`./scripts/dev.sh`。

打开 <http://127.0.0.1:3000>，点「构建索引」→ 输入查询（例如 `红色背景的产品截图`）→ 搜索。
也支持直接分享链接：`http://127.0.0.1:3000/?q=海边日落照片`。

### 配 Key（免费）

```bash
cd backend
cp .env.example .env      # 填入 GEMINI_API_KEY=...
```

Key 在 <https://aistudio.google.com/apikey> 免费申请。填完重启后端，界面上的
「理解后端 / 生成模型 / 向量模型」三个下拉框就会解锁。

## 模型策略（重要）

Gemini 模型名迭代很快，旧模型（`gemini-2.0-flash`、`text-embedding-004`）已被 Google 下线，
所以代码里**不写死**：

| 用途 | 默认 | 说明 |
| --- | --- | --- |
| 理解（多模态生成） | `gemini-3.6-flash` | 免费档；约 6~7s/图。备选 `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` / `gemini-3.8-flash` |
| 向量 | `gemini-embedding-2` | 免费档多模态向量模型，1536 维。备选 `gemini-embedding-001` |

- `backend/lumen/models.py` 会调 `ListModels` 自动发现当前 Key 真正可用的模型，界面里可直接下拉选择。
- **免费档配额按模型计**：每个模型每天约 20 次 `generate_content`。所以：
  1. **理解结果落盘缓存**（`data/understand_cache.json`，键 = 路径+mtime+大小）→ 改一次索引只花 0 次调用，二次构建 1.7s；
  2. **429 配额耗尽自动换模型**：某个模型配额用完，自动切到候选列表里的下一个模型继续跑（配额按模型算，换模型就能继续）；
  3. 只对瞬时错误（SSL/超时/5xx）重试，**配额错误不重试**（重试只会浪费配额）。
- 想要固定版本，在 `.env` 里写 `GEMINI_MODEL=` / `GEMINI_EMBED_MODEL=` 即可。

## 架构

```
gdg-dev/
├── backend/                     Python · FastAPI · LangChain
│   ├── lumen/
│   │   ├── config.py            路径 / 环境变量 / 后端自动选择
│   │   ├── models.py            Gemini 模型发现（ListModels）+ 候选链
│   │   ├── ingest.py            ① 采集：类型识别、主色、截图判定、文本抽取
│   │   ├── understand.py        ② 理解：LangChain Gemini（结构化输出）/ 离线兜底
│   │   ├── embed.py             ③ 向量：Gemini embeddings / 离线 hashing TF-IDF
│   │   ├── cache.py             理解结果落盘缓存（省配额的关键）
│   │   ├── index_store.py       ④ 落盘：records.json + vectors.npy + idf.json
│   │   ├── pipeline.py          编排 + 检索（语义相似度 + 关键词重排）
│   │   └── server.py            HTTP 接口
│   ├── scripts/make_sample_data.py
│   └── sample_data/             8 个离线测试样本（png/txt/md/docx）
├── frontend/                    Next.js 15 (App Router, TypeScript)
│   ├── app/                     页面 + 全局样式
│   ├── components/              Explorer（交互）/ ResultCard（结果卡）
│   └── lib/                     API 封装 + 类型
└── scripts/                     启动脚本
```

### 检索是怎么算分的

1. **语义相似度**：`标题 + 描述 + 标签 + OCR + 正文` 拼成一段文本 → 向量 → 与查询向量做 cosine。
2. **关键词重排**：查询分词后统计字面命中率加权（`final_score = semantic + keyword_bonus`）。
3. 两者叠加，"意思近"和"字面命中"都不丢。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 后端状态、Key 是否检测到、可用模型列表、已索引文件数 |
| POST | `/api/build` | `{root, backend, model?, embed_model?}` → 扫描 + 理解 + 向量化 + 落盘 |
| POST | `/api/search` | `{query, topk}` → 命中列表（分数、描述、标签、OCR、路径） |
| GET | `/api/thumb?path=` | 缩略图（仅限已索引文件） |
| GET | `/api/file?path=` | 原始文件（仅限已索引文件） |
| DELETE | `/api/index` | 清空索引 |

前端通过 `next.config.mjs` 的 rewrites 把 `/api/*` 代理到 `http://127.0.0.1:8000`，
需要改后端地址时设置 `NEXT_PUBLIC_API_BASE` 即可。

## 实测结果（真实 Gemini，8 个样本）

| 查询 | 命中 | 得分 |
| --- | --- | --- |
| 红色背景的产品截图 | 红色背景产品截图.png | 0.784 |
| 海边日落照片 | 海边日落.png | 0.779 |
| 含有发票的文档 | 发票说明.txt | 0.750 |
| 合同金额 | 合同摘要.docx | 0.900 |

Gemini 生成的描述示例：
> 「一幅简约风格的插画，展现了太阳在地平线上方落下或升起的黄昏或清晨的海景。」 标签：插画 / 风景 / 日出 / 日落 / 大海

离线模式（无 Key）也能命中，但描述只有"主色 + 尺寸 + OCR"这种浅层信息。

## 已知限制

- 免费档配额按模型计（每天 ~20 次/模型），所以**理解必须走缓存**；大量文件时建议分批或换模型。
- 首次索引是全量的，没有做增量扫描（PPT 里的"进阶"部分未实现）。
- 向量库是本地 numpy 稠密向量，文件量到万级需要换 Chroma/FAISS。
- PDF 只抽元信息，未解析正文。
- 图片理解走 JPEG 重编码上传，原始 PNG 的文字锐度会有一点损失。
