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

## 进阶设计思路

当前 demo 已经把数据流拆成了「采集 → 理解 → 向量 → 存储 → 检索」五个模块，后续扩展建议继续保持这个边界，不要把所有能力塞进 `pipeline.py`。

### 1. 持久化 / 增量索引：只处理新增和变化的文件

**目标**：第二次构建时不再扫描、理解、向量化全部文件，只处理新增、修改过的文件，并清理已删除文件。

建议增加一张文件清单（可以先用 SQLite，简单版本也可以继续用 JSON）：

```text
file_manifest
├── file_id          稳定 ID（path 的 hash）
├── path             绝对路径
├── size / mtime     快速判断文件是否变化
├── content_hash     可选，防止 mtime 被系统改写
├── status            active / deleted / failed
├── understand_model 本次使用的理解模型
├── vector_id        向量库中的 ID
└── updated_at
```

每次构建执行：`scan → diff → process dirty files → upsert vectors → tombstone deleted files → atomic snapshot`。
先用 `path + size + mtime` 做快速判断，只有疑似变化时再计算 hash；写入时使用临时文件 + rename，避免程序中断留下半个索引。
当前的 `understand_cache.json` 已经是这个方向的基础，但它只缓存理解结果，下一步需要把**文件状态、向量状态和删除状态**也纳入 manifest。

### 2. 换 Chroma / FAISS：支撑万级文件

当前 numpy 是全量暴力计算：文件越多，查询越慢。建议先定义一个稳定的向量库接口：

```python
class VectorIndex:
    def upsert(self, ids, vectors, metadatas): ...
    def delete(self, ids): ...
    def search(self, query_vector, top_k): ...
    def persist(self): ...
```

- **Chroma**：适合第一步升级。自带持久化、metadata 过滤和 collection 管理，改动小；文件档案可以放在 metadata 或 SQLite 中。
- **FAISS**：适合更大规模和更低延迟。推荐 `HNSW` 做原型，数据量稳定后再评估 IVF/PQ；必须额外维护 `vector_id → FileRecord` 的映射。
- 不管选哪个，都不要把完整文件内容塞进向量库；向量库只保存 `vector_id / embedding / 轻量 metadata`，详细档案仍由 `IndexStore` 或 SQLite 管理。
- 迁移时保留 `embedding_model`、`embedding_dim`、`distance_metric` 和 `index_version`，模型或维度变化时新建 collection，不要直接混写旧向量。

推荐路径：先抽象接口 → 用 Chroma 验证过滤和持久化 → 数据量达到瓶颈后再换 FAISS；业务层不应该感知具体向量库。

### 3. 私有部署 Gemma：本地多模态、零云依赖

**目标**：把当前 `GeminiUnderstander` 替换为本地 `GemmaUnderstander`，图片、文档和理解结果都不离开电脑。

建议沿用现有 `Understander` 接口，增加 provider 配置：

```text
understand_backend = gemini | gemma | offline
embed_backend      = gemini | local
```

实现上可以选择 Ollama、llama.cpp 或 vLLM 作为本地模型运行层；模型选择使用支持图像输入的 Gemma 多模态 checkpoint，具体模型名通过配置注入，不写死在业务代码里。调用层仍然只返回统一的：`description / tags / ocr_text`。

本地模式的处理链建议是：

```text
图片 → 本地 Gemma 视觉理解
文字 → 本地 Gemma 摘要/关键词
OCR  → tesseract（本地，作为补充）
向量 → 本地 embedding 模型
```

需要提前考虑：模型下载体积、显存/内存、量化版本、首次加载时间、CPU fallback，以及结构化 JSON 输出失败时的修复策略。隐私要求高的场景可以默认 `gemma`，禁止 `gemini`；普通用户则继续使用 Gemini 免费档。

### 4. 批量导入 + 定时重建：从一次性脚本变成后台任务

**目标**：用户提交多个目录后，系统在后台排队处理，不阻塞 HTTP 请求，并支持每天/每小时自动扫描。

建议拆成四层：

```text
API 层       POST /api/jobs、GET /api/jobs/{id}、POST /api/jobs/{id}/cancel
任务层       Job(id, root, status, progress, counters, error, started_at, finished_at)
执行层       scanner → understand workers → embed worker → commit snapshot
调度层       APScheduler + SQLite（单机）；规模变大再换 Redis/RQ/Celery
```

任务状态建议：`queued → scanning → processing → committing → completed`，异常走 `failed`，用户取消走 `cancelled`。每个文件单独记录 `pending / processing / done / failed`，这样程序崩溃后可以从 checkpoint 继续，而不是整批重来。

免费 Gemini 场景必须同时加入：

- 每模型 RPM/RPD 限流和 token bucket
- 429 不重试，切换候选模型
- SSL/超时/5xx 指数退避，最多 3 次
- 任务级并发上限
- 每批完成后保存 checkpoint
- 任务日志中记录模型、缓存命中数、失败数和预计剩余额度

定时重建不要直接启动第二个 build；使用目录级锁或 job key 去重，同一目录已有任务时合并请求。生产环境再加 webhook、邮件/站内通知和失败重跑按钮。

### 推荐实施顺序

```text
Phase 1  增量 manifest + 删除文件 tombstone + 原子写入
Phase 2  VectorIndex 抽象 + Chroma 持久化
Phase 3  后台 Job + checkpoint + APScheduler 定时任务
Phase 4  Gemma/Ollama 本地 provider + 本地 embedding
Phase 5  FAISS/HNSW、权限、多用户和监控
```

每一步都应保持现有 API 的输入输出不变，先替换内部实现，再升级前端。这样可以让当前 demo 持续可用，也能逐步演进成真正的本地文件检索服务。

## 已知限制

- 免费档配额按模型计（每天 ~20 次/模型），所以**理解必须走缓存**；大量文件时建议分批或换模型。
- 首次索引是全量的，没有做增量扫描（上面的进阶设计给出了实现路径）。
- 向量库是本地 numpy 稠密向量，文件量到万级需要换 Chroma/FAISS。
- PDF 只抽元信息，未解析正文。
- 图片理解走 JPEG 重编码上传，原始 PNG 的文字锐度会有一点损失。
