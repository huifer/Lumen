"""流水线编排：采集 → 理解 → 向量化 → 落盘；以及 检索 → 重排 → TopK。"""
from __future__ import annotations

import re
import time
from pathlib import Path

import numpy as np

from . import config
from .cache import UnderstandCache
from .embed import GeminiEmbedder, OfflineEmbedder, get_embedder, tokenize
from .index_store import IndexStore
from .ingest import scan
from .models import candidate_generation_models
from .pipeline_utils import redact
from .understand import get_understander


def searchable_text(rec) -> str:
    """把标题+描述+标签+OCR+正文拼成一段文本——这是命中质量的核心。"""
    return " ".join(
        str(x) for x in [
            rec.title,
            rec.description,
            " ".join(rec.tags),
            rec.ocr_text,
            rec.text[:2000],
            rec.dominant_color_name or "",
        ]
        if x
    )


def redact_local(text: str) -> str:
    """兼容旧调用。"""
    return redact(text)


def build(root: str, backend: str | None = None, store: IndexStore | None = None,
          gen_model: str | None = None, embed_model: str | None = None) -> dict:
    """全量构建索引。

    gen_model / embed_model 为空时自动发现当前 Key 可用的最新模型。
    Gemini 后端出错时自动降级为离线模式，保证 demo 永远能跑。
    """
    backend = (backend or config.DEFAULT_BACKEND).lower()
    try:
        return _build_once(root, backend, store, gen_model, embed_model)
    except Exception as exc:  # noqa: BLE001
        if backend == "offline":
            raise
        warning = redact(f"Gemini 后端不可用，已自动降级为离线模式：{exc}")
        result = _build_once(root, "offline", store, None, None)
        result["degraded"] = True
        result["warning"] = warning
        return result


def _build_once(root: str, backend: str, store: IndexStore | None,
                gen_model: str | None, embed_model: str | None) -> dict:
    cache = UnderstandCache()
    candidates = candidate_generation_models(preferred=gen_model) if backend == "gemini" else []
    understander = get_understander(backend, model=gen_model, candidates=candidates, cache=cache)
    embedder = get_embedder(backend, model=embed_model)
    started = time.time()

    records = scan(root)
    if not records:
        raise RuntimeError(f"目录里没有可索引的文件: {root}")

    # 1) 理解（并发跑，Gemini 单文件约 6~20s，并行能大幅缩短总耗时）
    def understand_one(rec):
        result = understander.understand(rec)
        rec.description = result.get("description", "")
        rec.tags = result.get("tags", [])
        rec.ocr_text = result.get("ocr_text", "")

    if backend == "gemini" and len(records) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(3, len(records))) as pool:
            list(pool.map(understand_one, records))
    else:
        for rec in records:
            understand_one(rec)
    cache.save()

    # 2) 向量化（离线需要先在语料上 fit IDF）
    texts = [searchable_text(rec) for rec in records]
    if isinstance(embedder, OfflineEmbedder):
        embedder.fit(texts)
    vectors = embedder.transform_many(texts)

    # 3) 落盘
    if store is None:
        store = IndexStore()
    store.clear()
    for rec, vec in zip(records, vectors):
        store.add(rec, vec)
    store.meta = {
        "backend": backend,
        "understander": understander.name,
        "understand_model": getattr(understander, "model", understander.name),
        "root": str(Path(root).expanduser().resolve()),
        "embedder": embedder.state_dict(),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(records),
    }
    store.save()

    return {
        "ok": True,
        "backend": backend,
        "understander": understander.name,
        "count": len(records),
        "root": store.meta["root"],
        "elapsed_ms": int((time.time() - started) * 1000),
        "degraded": False,
        "warning": None,
        "models_used": getattr(understander, "used_models", {}),
        "quota_exhausted": list(getattr(understander, "quota_exhausted", [])),
        "cache_entries": len(cache),
        "files": [_file_summary(r) for r in records],
    }


def search(query: str, topk: int = 8, store: IndexStore | None = None,
           backend: str | None = None) -> dict:
    """语义相似度 + 关键词重排。"""
    store = store if store is not None else IndexStore()
    if not store.load():
        return {"ok": False, "error": "索引为空，请先构建索引", "hits": []}

    backend = (backend or store.meta.get("backend") or config.DEFAULT_BACKEND).lower()
    stored = store.meta.get("embedder") or {}
    if backend == "gemini" and config.GEMINI_API_KEY:
        # 用建索引时记录的那个模型，保证向量维度一致
        embedder = GeminiEmbedder(model=stored.get("model"))
    elif stored and backend == "offline":
        embedder = OfflineEmbedder.from_state(stored)
    else:
        embedder = get_embedder(backend)

    started = time.time()
    q_vec = embedder.transform(query)
    if len(store.records) and store.vectors.shape[1] != q_vec.shape[0]:
        return {
            "ok": False,
            "error": "索引向量维度与当前模型不一致，请重新构建索引",
            "hits": [],
        }
    sims = store.vectors @ q_vec if len(store.records) else np.zeros(0)
    sims = np.asarray(sims, dtype=np.float32)

    hits = []
    for rec, sim in zip(store.records, sims):
        keyword_bonus = keyword_score(query, rec)
        hits.append(
            {
                "score": round(float(sim), 4),
                "keyword_bonus": round(keyword_bonus, 4),
                "final_score": round(float(sim) + keyword_bonus, 4),
                **_file_summary(rec),
            }
        )

    hits.sort(key=lambda h: h["final_score"], reverse=True)
    hits = hits[:topk]
    return {
        "ok": True,
        "query": query,
        "backend": store.meta.get("backend", backend),
        "took_ms": int((time.time() - started) * 1000),
        "total": len(store.records),
        "hits": hits,
    }


def keyword_score(query: str, rec) -> float:
    """字面命中加权：查询词是否出现在档案文本里。"""
    text = searchable_text(rec).lower()
    tokens = [t for t in tokenize(query) if len(t) >= 2]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in text)
    return round(0.05 * hits / len(tokens) * 4, 4)


def _file_summary(rec) -> dict:
    return {
        "path": rec.path,
        "rel_path": rec.rel_path,
        "name": rec.name,
        "ext": rec.ext,
        "kind": rec.kind,
        "size": rec.size,
        "mtime": rec.mtime,
        "width": rec.width,
        "height": rec.height,
        "dominant": rec.dominant,
        "dominant_color_name": rec.dominant_color_name,
        "dominant_ratio": rec.dominant_ratio,
        "is_screenshot": rec.is_screenshot,
        "title": rec.title,
        "description": rec.description,
        "tags": rec.tags,
        "ocr_text": rec.ocr_text,
        "text_preview": (rec.text or "")[:300],
    }
