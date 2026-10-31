# Lumen Development Guide

> For developers who want to read, modify, or build on top of this codebase. Assumes you already have the system running (see the [User Manual](./user-manual.en.md)). After reading this you will know: how data flows, what every file is responsible for, and where to change what.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Directory Structure: What Every File Does](#3-directory-structure-what-every-file-does)
4. [Core Workflows in Detail](#4-core-workflows-in-detail)
5. [HTTP API Reference](#5-http-api-reference)
6. [On-disk Data Formats](#6-on-disk-data-formats)
7. [Gemini Integration Details & Free-tier Constraints](#7-gemini-integration-details--free-tier-constraints)
8. [Common Extension Tasks (How To)](#8-common-extension-tasks-how-to)
9. [Frontend Structure & Modification Guide](#9-frontend-structure--modification-guide)
10. [Development Environment & Debugging Tips](#10-development-environment--debugging-tips)
11. [Advanced Design & Roadmap](#11-advanced-design--roadmap)

---

## 1. Tech Stack

| Layer | Technology | Version | Notes |
| --- | --- | --- | --- |
| Frontend | Next.js (App Router) + React + TypeScript | 15.5.28 / 19 | No UI library; hand-written CSS (`globals.css`) |
| FE/BE wiring | Next.js rewrites | — | `/api/*` proxied to the backend; zero CORS configuration in frontend code |
| Backend | Python + FastAPI + uvicorn | 3.10 / fastapi 0.13x | Synchronous endpoints (fine at demo scale) |
| AI | LangChain + `langchain-google-genai` | 4.x | `ChatGoogleGenerativeAI` + `GoogleGenerativeAIEmbeddings` |
| Vector store | numpy dense vectors (local files) | — | Brute-force cosine scan; fine below ~10k documents |
| OCR | tesseract CLI (subprocess) | 5.x | Chinese requires the `chi_sim` language pack |
| Imaging | Pillow | 12.x | Dominant color, thumbnails, screenshot detection, JPEG re-encoding |

**Design principles**: one responsibility per file; modules communicate only through the `FileRecord` dataclass; every fallible AI call has a degradation path so the demo always produces a result.

---

## 2. Architecture & Data Flow

```
Browser
  │  http://127.0.0.1:3000
  ▼
Next.js frontend (app/, components/)
  │  fetch('/api/...')                    ← same-origin requests, no CORS
  │  proxied by next.config.mjs rewrites
  ▼
FastAPI backend (lumen/server.py, :8000)
  │
  ├─ POST /api/build ──▶ pipeline.build()
  │      ① ingest.scan()              scan directory → [FileRecord] (local IO only)
  │      ② understander.understand()  concurrent (3 threads) Gemini / offline fallback
  │      ③ embedder.transform_many()  text → vectors (Gemini / offline hashing TF-IDF)
  │      ④ index_store.save()         persist records + vectors + idf
  │
  └─ POST /api/search ─▶ pipeline.search()
         q_vec = embed(query)
         hits  = cosine(index vectors) + keyword_bonus (literal-hit boost)
         sort and take TopK
```

**Key concept: three "configuration sources" drive backend behavior**

1. `backend/.env` → loaded by `config.py` (`GEMINI_API_KEY`, model names, OCR settings)
2. The `ListModels` API → `models.py` discovers which models the key can actually use (10-minute cache)
3. Parameters passed in from the UI (`backend` / `model` / `embed_model`) → override the defaults

---

## 3. Directory Structure: What Every File Does

```
gdg-dev/
├── README.md
├── docs/                        The manuals (this document)
├── scripts/                     Start-up scripts (bash)
│   ├── start-backend.sh         Create venv (if missing) + launch uvicorn
│   ├── start-frontend.sh        npm install (if missing) + next dev
│   └── dev.sh                   Generate samples + start both servers
│
├── backend/
│   ├── requirements.txt
│   ├── .env.example             Config template (.env is the real local config, gitignored)
│   ├── scripts/make_sample_data.py   Generate 8 test samples (Pillow drawings + hand-built docx)
│   ├── sample_data/             Test samples: 4 images + 3 text files + 1 docx
│   ├── data/                    [Generated at runtime, gitignored] index & caches
│   │   ├── index.json           File records + metadata
│   │   ├── vectors.npy          All vectors (row-aligned with index.json)
│   │   ├── idf.json             IDF table for offline TF-IDF
│   │   ├── understand_cache.json Understanding cache (key to saving quota)
│   │   └── thumbs/              Thumbnail cache (md5(path).jpg)
│   └── lumen/
│       ├── config.py            Constants + .env loading + backend auto-selection
│       ├── models.py            Gemini model discovery (ListModels) + candidate chain + version ordering
│       ├── ingest.py            ① Ingest: scan / extract_meta / dominant_color / is_ui_screenshot
│       ├── understand.py        ② Understand: GeminiUnderstander / OfflineUnderstander
│       ├── embed.py             ③ Embed: GeminiEmbedder / OfflineEmbedder
│       ├── cache.py             Understanding cache (key = sha1(path|mtime|size))
│       ├── index_store.py       ④ Persistence: IndexStore (records + vectors CRUD)
│       ├── pipeline.py          build/search orchestration + scoring + redact
│       ├── pipeline_utils.py    Small utilities (redact: scrub secrets from errors)
│       └── server.py            FastAPI routes (build/search/health/thumb/file/reset)
│
└── frontend/
    ├── next.config.mjs          rewrites /api/* → 127.0.0.1:8000
    ├── package.json             next 15.5.28 (fixes CVE-2025-66478)
    ├── app/
    │   ├── layout.tsx           Root layout + metadata
    │   ├── page.tsx             Home page (Server Component, wrapped in Suspense)
    │   └── globals.css          All styles (dark theme via CSS variables)
    ├── components/
    │   ├── Explorer.tsx         The only interactive component (state machine, 'use client')
    │   └── ResultCard.tsx       Result card (presentational)
    └── lib/
        ├── api.ts               fetch wrappers + thumbUrl/fileUrl
        └── types.ts             TS types aligned with backend JSON
```

### The single data contract across modules: `FileRecord`

Defined in `ingest.py`, passed through the whole pipeline, serialized straight into index.json via `to_dict()`:

```python
@dataclass
class FileRecord:
    path / rel_path / name / ext / kind      # identity (kind: image|pdf|doc|text|other)
    size / mtime / width / height            # metadata
    dominant / dominant_color_name / dominant_ratio / is_screenshot   # visual features
    text                                     # text snippet for text-like files (≤8000 chars)
    title / description / tags / ocr_text    # filled in by the understand stage
```

**Adding a field means touching exactly this** (+ `_file_summary` in pipeline + `types.ts` on the frontend). This is the most important extension point in the project.

---

## 4. Core Workflows in Detail

### 4.1 build (`pipeline.build` → `_build_once`)

```python
def build(root, backend=None, store=None, gen_model=None, embed_model=None):
    try:
        return _build_once(root, backend, store, gen_model, embed_model)
    except Exception as exc:
        if backend == "offline":
            raise
        # Total Gemini failure → rebuild offline, return result with a warning
        result = _build_once(root, "offline", store, None, None)
        result["degraded"] = True
        result["warning"] = redact(f"Gemini backend unavailable, fell back to offline mode: {exc}")
        return result
```

The four steps inside `_build_once`:

1. **Understand** (concurrent): `ThreadPoolExecutor(max_workers=3)`. Per file:
   - Check cache `cache.get(rec, model)` → on hit, return immediately (**0 API calls**)
   - On miss → try the candidate model chain in order → `cache.put()` on success
2. **Embed**: `texts = [searchable_text(rec) for rec in records]`, where
   `searchable_text = title + description + tags + ocr_text + text[:2000] + dominant color name` — **this is the core of retrieval quality**.
   The offline embedder must `fit(texts)` first to compute IDF; Gemini embeds in batches directly.
3. **Persist**: `store.clear()`, then `add(rec, vec)` per record, finally `save()` (json + npy + idf).
4. **Return stats**: `models_used` (call count per model), `quota_exhausted`, `cache_entries` — passed straight through to the frontend.

### 4.2 search (`pipeline.search`)

```
final_score = cosine(query_vector, doc_vector) + keyword_bonus
# keyword_bonus = 0.05 * (matched tokens / query tokens) * 4  →  at most +0.20
```

- The query vector and index vectors must come from **the same model** — the model used at build time is recorded in `store.meta["embedder"]["model"]` and search reuses it, preventing dimension mismatches.
- On dimension mismatch, a business error "please rebuild the index" is returned instead of a 500.
- Offline mode: rebuilds `OfflineEmbedder` from the idf table in `store.meta["embedder"]` so query and document weights stay consistent.

### 4.3 The dual-backend understander (`understand.py`)

```
GeminiUnderstander                        OfflineUnderstander
├─ Candidate model chain (auto-switch     ├─ Images: dominant color + size +
│  on quota exhaustion)                   │  screenshot heuristic + tesseract OCR
├─ with_structured_output(SCHEMA)         ├─ Documents: first sentences + 2-gram keywords
├─ SystemMessage forces Chinese output    └─ Never touches the network, never raises
├─ _retry(): retries SSL/timeout/5xx only
└─ 429 → mark model → try next candidate
Both fail → return offline result + " (Gemini call failed, fell back to offline understanding)" suffix
```

**Why 429 is never retried**: on the free tier the `retryDelay` for a 429 is ~22 hours; retrying just burns more attempts.
**Why the cache key excludes the model name**: rebuilding with a different model can reuse old results, so the same file never costs quota twice.

### 4.4 Model discovery (`models.py`)

- `list_models(api_key)`: `GET /v1beta/models` → splits models into generation / embedding groups by `supportedGenerationMethods`, cached for 10 minutes.
- `resolve_generation_model()`: explicit `.env` value > preference list (3.6-flash → 3.5-flash-lite → 3.1-flash-lite → 3.8-flash …) > fallback constant.
- `candidate_generation_models()`: builds the **ordered candidate chain** (preferred + preference list + remaining flash models by version desc) used to rotate on 429 during understanding.
- `_pick()` fallback: if nothing in the preference list is available, pick the highest-version flash model from what is available.

---

## 5. HTTP API Reference

All endpoints live under `/api` and speak JSON. The backend ships a Swagger UI at **http://127.0.0.1:8000/docs** where you can try everything from the browser.

### GET /api/health

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{
  "ok": true,
  "default_backend": "gemini",
  "key_present": true,
  "models": {
    "generation": "gemini-3.6-flash",
    "embedding": "gemini-embedding-2",
    "generation_available": ["gemini-3.6-flash", "... 46 models"],
    "embedding_available": ["gemini-embedding-2", "gemini-embedding-001"],
    "error": null
  },
  "indexed_files": 8,
  "state": { "status": "ready", "message": "Index built, 8 files" }
}
```

### POST /api/build

```bash
curl -X POST http://127.0.0.1:8000/api/build \
  -H 'Content-Type: application/json' \
  -d '{"root": "sample_data", "backend": "gemini"}'
# Optional fields: model (generation model), embed_model (embedding model)
```

Success:

```json
{
  "ok": true, "backend": "gemini", "understander": "gemini",
  "count": 8, "elapsed_ms": 47268,
  "models_used": { "gemini-3.5-flash-lite": 8 },
  "quota_exhausted": ["gemini-3.6-flash"],
  "cache_entries": 8,
  "degraded": false, "warning": null,
  "files": [ { "path": "...", "description": "...", "tags": ["..."] } ]
}
```

Failure: HTTP 400 + `{"detail": "reason"}` (redacted; the API key never leaks).

### POST /api/search

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "product screenshot with a red background", "topk": 3}'
```

```json
{
  "ok": true, "query": "product screenshot with a red background", "backend": "gemini",
  "took_ms": 940, "total": 8,
  "hits": [{
    "score": 0.734,
    "keyword_bonus": 0.05,
    "final_score": 0.784,
    "name": "red-product-screenshot.png", "kind": "image",
    "description": "A product launch page wireframe with a red border...",
    "tags": ["UI design", "wireframe", "red"], "ocr_text": "Product Launch ...",
    "path": "/abs/path", "rel_path": "red-product-screenshot.png", "size": 6600
  }]
}
```

### Others

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/thumb?path=<abs path>` | Thumbnail (480px JPEG). **Indexed files only**, else 403; unreadable → 415 |
| GET | `/api/file?path=<abs path>` | Raw file (used by "open original file") |
| DELETE | `/api/index` | Clears the index records (keeps the understanding cache) |

> Security boundary: thumb/file both require the path to exist in the current index, so the service can't be turned into an arbitrary file downloader.

---

## 6. On-disk Data Formats

### index.json

```json
{
  "meta": {
    "backend": "gemini", "understander": "gemini",
    "understand_model": "gemini-3.5-flash-lite",
    "root": "/abs/scan/root", "built_at": "2026-10-28 16:10:00", "count": 8,
    "embedder": { "model": "gemini-embedding-2", "dim": 1536 }
  },
  "records": [ { "note": "FileRecord.to_dict() x N, order-aligned with vector rows" } ]
}
```

### understand_cache.json

```json
{
  "note": "key = sha1(path|mtime|size)",
  "entry": {
    "path": "/abs/file.png", "model": "gemini-3.5-flash-lite",
    "at": "2026-10-28 16:09:00",
    "description": "...", "tags": ["..."], "ocr_text": "..."
  }
}
```

> Caution: row order of vectors.npy = order of records = the order of `IndexStore.add` calls. Any change that reorders records requires a full rebuild (or updating the alignment logic in the store).

---

## 7. Gemini Integration Details & Free-tier Constraints

### 7.1 The real free-tier constraints (measured 2026-10)

| Fact | Impact on the code |
| --- | --- |
| Quota is counted **per model**: ~20 generate requests/day/model (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) | On 429, switch to the next candidate model and keep going (candidate chain in `understand.py`) |
| Multiple keys belong to the same project → shared quota | Adding keys doesn't help; adding model variety does |
| 429 retryDelay ≈ 22h | **Never retry a 429**; only retry SSL/timeout/5xx (≤3 attempts) |
| Embedding quota is separate and generous | Embedding needs no special handling |
| Concurrency + retries burn quota fast | Concurrency capped at 3; cache as backstop |

### 7.2 LangChain usage notes (pitfalls we hit)

```python
# ① Images: must use the OpenAI-compatible nested format; the flat form raises KeyError: 'image_url'
{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
# Equivalent alternative: {"type": "media", "mime_type": "image/jpeg", "data": <bytes>}

# ② Structured output: pass a dict schema; the result comes back as a parsed dict
llm.with_structured_output(IMAGE_SCHEMA).invoke([SystemMessage(...), HumanMessage(...)])

# ③ Gemini 3.x fixes sampling params: passing temperature is ignored with a warning → don't pass it

# ④ Gemini 3.x drifts into English by default → a SystemMessage forces Chinese (SYSTEM_PROMPT)

# ⑤ Re-encode images to JPEG before upload (bmp/tiff are rejected; also smaller payloads)
image_as_jpeg_base64(path)   # understand.py

# ⑥ Embeddings: gemini-embedding-001 supports 768/1536/3072 dims; task_type differs for docs vs queries
GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2",
                             google_api_key=KEY,
                             task_type="RETRIEVAL_DOCUMENT",   # use RETRIEVAL_QUERY on the query side
                             output_dimensionality=1536)
```

### 7.3 Model names expire

`text-embedding-004` (shut down 2026-01), `gemini-2.0-flash` (shut down 2026-06).
So we **never hard-code names**: runtime discovery via `ListModels` + preference list + fallback constant, three layers deep. Currently verified working combos:

| Purpose | First choice | Alternatives |
| --- | --- | --- |
| Understanding | `gemini-3.6-flash` (6–7s/image, stable) | `gemini-3.5-flash-lite` (5s/image), `gemini-3.1-flash-lite`, `gemini-3.8-flash` (short-term availability, volatile) |
| Embedding | `gemini-embedding-2` (multimodal, 1536/3072 dims) | `gemini-embedding-001` (text-only GA) |

---

## 8. Common Extension Tasks (How To)

### 8.1 Support a new file type (e.g. `.rst`, `.ppt`)

1. `config.py`: add the extension to `TEXT_EXT` / `DOC_EXT` / `IMAGE_EXT`
2. Text-like → done (`ingest.extract_meta` reads the text directly)
3. OOXML (pptx/docx/xlsx) → add a name filter rule in `ingest.extract_ooxml_text`
4. Binary formats (e.g. pdf body) → add a branch in `extract_meta` and stuff text into `meta["text"]`
5. Rebuild the index

### 8.2 Change the AI description style / prompts

Everything lives at the top of `understand.py`: `IMAGE_SCHEMA`, `DOC_SCHEMA`, `SYSTEM_PROMPT`, plus the prompt text inside `_image` / `_document`. After changing, **delete that file's cache** (or `rm data/understand_cache.json`) before rebuilding, otherwise stale cache wins.

### 8.3 Switch / add generation models

- Ad hoc: pick in the UI dropdown, or pass `model` in `POST /api/build`
- Permanent default: `GEMINI_MODEL` / `GEMINI_EMBED_MODEL` in `config.py` (or .env)
- Candidate chain order: `PREFERRED_GEN_MODELS` in `models.py`

### 8.4 Swap the vector store (Chroma / FAISS)

Only two call sites change; the interface stays the same:

- Write: step 3 of `pipeline._build_once` (currently `IndexStore.add/save`)
- Query: `pipeline.search` (currently `store.vectors @ q_vec`

Recommended: implement a class with the same shape as `IndexStore` (`add/save/load/clear/__len__` + `top_k(vec, k)`) and select it via config in `pipeline`. Preserve the alignment between `records` and vectors.

### 8.5 Incremental indexing (only process new/changed files)

The cache is already keyed by `path+mtime+size`, so this is natural — incremental = after scan, load the old index.json, skip files whose cache entry hits and whose mtime/size are unchanged, understand only the new ones. The change lives in step 1 of `_build_once`: load the old store and diff.

### 8.6 More parallelism / rate limiting

`ThreadPoolExecutor(max_workers=3)` in `_build_once`. Mind free-tier RPM before raising it; a better approach is a simple token bucket (a `time.sleep` throttle is enough).

### 8.7 Add a new API endpoint

Copy the pattern in `server.py`:

```python
class XxxRequest(BaseModel):
    ...

@app.post("/api/xxx")
def xxx(req: XxxRequest) -> dict:
    ...
```

Note: run anything that might contain paths/exceptions through `redact()`.

---

## 9. Frontend Structure & Modification Guide

### Data flow

```
Explorer.tsx ('use client')
  useEffect        → api.health()      → health state (backend/model lists/indexed count)
  handleBuild      → api.build(...)    → buildResult + refresh health
  handleSearch     → api.search(...)   → result.hits → render ResultCard list
  useSearchParams  → ?q=xxx auto-searches on first load (page.tsx wraps Explorer in Suspense)
  router.replace   → writes ?q= back into the URL after a successful search (shareable)
```

### Where to change what in the UI

| I want to change... | File |
| --- | --- |
| Title/copy | `app/page.tsx` (hero section) |
| Colors/radius/spacing | `:root` CSS variables at the top of `app/globals.css` |
| Example query chips | the `EXAMPLES` constant in `Explorer.tsx` |
| Result card layout | `components/ResultCard.tsx` |
| Show a new field (e.g. mtime) | `ResultCard.tsx` + the `Hit` type in `lib/types.ts` |

### Conventions

- `Explorer.tsx` is the only component that needs `'use client'`; keep `page.tsx` a Server Component
- Images use plain `<img>` (thumbnails come from a dynamic endpoint; `next/image` optimization doesn't fit), eslint-disabled inline
- List rendering must carry a `key` (currently `hit.path`)
- Conditional rendering uses ternaries instead of `&&` (project convention)
- Type changes: backend response changed → update `lib/types.ts` first; `npx tsc --noEmit` finds every follow-up spot for you

---

## 10. Development Environment & Debugging Tips

### Common commands

```bash
# Backend (with hot reload)
cd backend && .venv/bin/python -m uvicorn lumen.server:app --reload --port 8000

# Frontend type check (run after any TS change)
cd frontend && npx tsc --noEmit

# Frontend production build (verification only; ⚠️ do NOT run while next dev is up — they clobber each other's .next)
cd frontend && npm run build

# Regenerate test samples
cd backend && .venv/bin/python scripts/make_sample_data.py

# Tail backend logs (understanding failures/degradations log warnings)
tail -f /tmp/lumen-api.log     # or the terminal where the backend is running
```

### Debugging playbook

1. **Poor search quality** → check the file's `description/tags/ocr_text` in index.json first;
   then check which component of `final_score` is dragging (semantic `score` vs literal `keyword_bonus`)
2. **Wrong understanding output** → check whether an old cache entry won (`at` field in `data/understand_cache.json`)
3. **Suspect quota** → `curl /api/health` for `models`; build responses carry `models_used` / `quota_exhausted`
4. **Unit-test Gemini directly**, skipping HTTP:

   ```bash
   cd backend && PYTHONPATH=. .venv/bin/python -c "
   from lumen.understand import get_understander
   from lumen.ingest import scan
   u = get_understander('gemini')
   print(u.understand(scan('sample_data')[0]))
   "
   ```

### Commit conventions (this repo)

- Before committing: confirm `git status` shows no `backend/.env` or `backend/data/` (.gitignore covers both; never `-f` them in)
- Anything touching errors/logs: confirm no API key is printed (`redact()` is the only outlet)

---

## 11. Advanced Design & Roadmap

The core boundary of the current demo is: **ingest → understand → embed → store → search**. Future upgrades should keep this boundary; don't stuff incrementals, vector stores, scheduling, and model adapters all into `pipeline.py`.

### 11.1 Persistence / incremental indexing: only process new and changed files

**Goal**: the second build processes only added/modified files and cleans up deleted ones.

Add a `file_manifest` (SQLite for v1; plain JSON is fine for a simple version):

```
file_manifest
├── file_id          stable ID (hash of path)
├── path             absolute path
├── size / mtime     fast change detection
├── content_hash     optional, guards against mtime being rewritten
├── status           active / deleted / failed
├── understand_model model used for this file
├── vector_id        ID in the vector store
└── updated_at
```

The build becomes:

```
scan → diff → process dirty files → upsert vectors
     → tombstone deleted files → atomic snapshot
```

Use `path + size + mtime` for fast checks; compute content hash only on suspicion of change. Write via temp file + `rename` so an interrupted process never leaves half an index. The current `understand_cache.json` is the foundation, but file status, vector status, and deletion status need to live in the manifest.

### 11.2 Chroma / FAISS: supporting tens of thousands of files

numpy is brute-force full scans — more files, slower queries. Define a stable vector-store interface first; the business layer shouldn't know the implementation:

```python
class VectorIndex:
    def upsert(self, ids, vectors, metadatas): ...
    def delete(self, ids): ...
    def search(self, query_vector, top_k): ...
    def persist(self): ...
```

- **Chroma**: the recommended first step. Built-in persistence, metadata filtering, and collection management; low migration cost.
- **FAISS**: for larger scale and lower latency. Start with HNSW; evaluate IVF/PQ once the dataset stabilizes; maintain an extra `vector_id → FileRecord` mapping.
- The vector store holds only `vector_id / embedding / light metadata`; full records stay in IndexStore or SQLite.
- Track `embedding_model / embedding_dim / distance_metric / index_version`; when model or dims change, create a new collection instead of mixing old vectors.

Recommended order: abstract the interface → validate filtering & persistence with Chroma → switch to FAISS at scale.

### 11.3 Self-hosted Gemma: local multimodal, zero cloud dependency

**Goal**: add a `GemmaUnderstander` alongside `GeminiUnderstander` so images, documents, and understanding results never leave the machine.

Keep the existing `Understander` interface and add provider config:

```
understand_backend = gemini | gemma | offline
embed_backend      = gemini | local
```

Runtime options: Ollama, llama.cpp, or vLLM; model names come from config, never hard-coded. Whatever the backend, the caller receives the same: `description / tags / ocr_text`.

```
Images   → local Gemma visual understanding
Text     → local Gemma summary/keywords
OCR      → tesseract (local supplement)
Vectors  → local embedding model
```

Evaluate model size, VRAM/RAM, quantized variants, first-load latency, CPU fallback, and JSON-repair when structured output fails. Privacy-sensitive deployments default to `gemma` and disable `gemini`; everyone else keeps the Gemini free tier.

### 11.4 Batch import + scheduled rebuilds: from one-shot script to background jobs

**Goal**: queue multiple directories without blocking HTTP, with hourly/daily auto scans.

Four layers:

```
API layer        POST /api/jobs, GET /api/jobs/{id}, POST /api/jobs/{id}/cancel
Job layer        Job(id, root, status, progress, counters, error, timestamps)
Execution layer  scanner → understand workers → embed worker → commit snapshot
Scheduler        APScheduler + SQLite (single node); move to Redis/RQ/Celery at scale
```

States: `queued → scanning → processing → committing → completed`; failures are `failed`, user cancellations `cancelled`. Track `pending / processing / done / failed` per file so a crash resumes from a checkpoint instead of redoing the batch.

For the free Gemini tier, also add:

- Per-model RPM/RPD rate limiting with a token bucket
- 429 → never retry, switch candidate model
- Exponential backoff (max 3) for SSL/timeout/5xx
- A job-level concurrency cap
- Checkpoint saves after each batch
- Logging of model usage, cache hits, failures, and estimated remaining quota

Scheduled rebuilds must not start a second build directly: use a directory lock or job key for dedup and merge requests for the same directory. Production can add webhooks, notifications, and a retry button.

### 11.5 Recommended implementation order

```
Phase 1  incremental manifest + delete tombstones + atomic writes
Phase 2  VectorIndex abstraction + Chroma persistence
Phase 3  background jobs + checkpoints + APScheduler scheduling
Phase 4  Gemma/Ollama local provider + local embeddings
Phase 5  FAISS/HNSW, permissions, multi-user, monitoring
```

Keep the existing API contract unchanged at every step: replace internals first, upgrade the frontend after. That keeps the current demo alive while it grows into a real local file search service.

### 11.6 Current known limitations

| Status | Impact | Direction |
| --- | --- | --- |
| Full index only, no incrementals | Wasteful rebuilds on big directories (cache already caps API cost) | Add manifest + diff per 11.1 |
| numpy brute-force cosine | Seconds-level latency at 10k files | Chroma/FAISS per 11.2 |
| PDF body not parsed | Only filenames searchable | pypdf → `FileRecord.text` |
| Synchronous endpoints | Large builds hold the request | Background jobs per 11.4 |
| JPEG re-encoding of images | Slight OCR detail loss | `media_resolution` / original upload |
| Single machine, single user | Not for team sharing | Permissions & multi-user later |
