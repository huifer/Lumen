"""FastAPI 服务：给 Next.js 前端提供建索引 / 搜索 / 缩略图接口。"""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageFile
from pydantic import BaseModel

from . import config
from .index_store import IndexStore
from .models import catalog_snapshot, resolve_embedding_model, resolve_generation_model
from .pipeline import build, redact, search

ImageFile.LOAD_TRUNCATED_IMAGES = True

app = FastAPI(title="Lumen API", description="本地多模态文件检索 · 后端")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = IndexStore()
_lock = threading.Lock()
_index_state: dict = {"status": "empty", "message": "尚未构建索引"}


class BuildRequest(BaseModel):
    root: str | None = None
    backend: str | None = None
    model: str | None = None
    embed_model: str | None = None


class SearchRequest(BaseModel):
    query: str
    topk: int = 8
    backend: str | None = None


@app.get("/api/health")
def health() -> dict:
    with _lock:
        count = len(store.records)
        meta = dict(store.meta)
    catalog = catalog_snapshot()
    return {
        "ok": True,
        "service": "lumen",
        "default_backend": config.DEFAULT_BACKEND,
        "key_present": bool(config.GEMINI_API_KEY),
        "models": {
            "generation": resolve_generation_model() if config.GEMINI_API_KEY else None,
            "embedding": resolve_embedding_model() if config.GEMINI_API_KEY else None,
            "generation_available": catalog.get("generation_available", []),
            "embedding_available": catalog.get("embedding_available", []),
            "available": catalog.get("available", []),
            "error": catalog.get("error"),
        },
        "indexed_files": count,
        "index_meta": meta,
        "state": _index_state,
        "sample_root": config.DEFAULT_SCAN_ROOT,
    }


@app.post("/api/build")
def build_index(req: BuildRequest) -> dict:
    root = req.root or config.DEFAULT_SCAN_ROOT
    backend = req.backend or config.DEFAULT_BACKEND
    try:
        with _lock:
            _index_state.update({"status": "building", "message": f"正在索引 {root}"})
            result = build(
                root,
                backend=backend,
                store=store,
                gen_model=req.model or None,
                embed_model=req.embed_model or None,
            )
            result["model"] = store.meta.get("embedder", {}).get("model")
            result["understand_model"] = store.meta.get("understand_model")
            _index_state.update(
                {
                    "status": "ready",
                    "message": f"索引完成，共 {result['count']} 个文件",
                    "built_at": store.meta.get("built_at"),
                }
            )
        return result
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _index_state.update({"status": "error", "message": redact(str(exc))})
        raise HTTPException(status_code=400, detail=redact(str(exc))) from exc


@app.post("/api/search")
def do_search(req: SearchRequest) -> dict:
    query = (req.query or "").strip()
    if not query:
        return {"ok": False, "error": "查询不能为空", "hits": []}
    try:
        with _lock:
            return search(query, topk=max(1, min(req.topk, 50)), store=store, backend=req.backend)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=redact(str(exc))) from exc


@app.get("/api/thumb")
def thumbnail(path: str) -> FileResponse:
    """返回图片缩略图（生成后缓存到 data/thumbs）。"""
    target = Path(path)
    known = {r.path for r in store.records}
    if str(target) not in known:
        raise HTTPException(status_code=403, detail="该文件不在索引内")

    config.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    cache = config.THUMB_DIR / f"{hashlib.md5(str(target).encode()).hexdigest()}.jpg"
    if not cache.exists():
        try:
            with Image.open(target) as img:
                img = img.convert("RGB")
                img.thumbnail((480, 480))
                img.save(cache, quality=82)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=415, detail="无法生成缩略图") from exc
    return FileResponse(cache, media_type="image/jpeg")


@app.get("/api/file")
def raw_file(path: str) -> FileResponse:
    target = Path(path)
    if str(target) not in {r.path for r in store.records}:
        raise HTTPException(status_code=403, detail="该文件不在索引内")
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件已不存在")
    return FileResponse(target)


@app.delete("/api/index")
def reset_index() -> dict:
    with _lock:
        store.clear()
        _index_state.update({"status": "empty", "message": "索引已清空"})
    return {"ok": True}
