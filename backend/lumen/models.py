"""Gemini 模型发现与解析。

Gemini 的模型 ID 迭代很快（2.0 → 2.5 → 3.x，旧模型随时被停用），
所以这里不写死模型名，而是：

1. 启动时调用 ListModels 接口拿到当前 Key 真正可用的模型；
2. 按偏好列表挑一个"多模态 + 快 + 便宜"的生成模型和一个向量模型；
3. 环境变量 GEMINI_MODEL / GEMINI_EMBED_MODEL 一旦显式指定，永远优先。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

from . import config

# 偏好顺序：先快且稳的 3.6 Flash，再 3.8 Flash（短期可用模型），最后是 Lite 系列
PREFERRED_GEN_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

# 偏好顺序：Gemini Embedding 2 是最新的多模态向量模型，001 是文本向量 GA
PREFERRED_EMBED_MODELS = [
    "gemini-embedding-2",
    "gemini-embedding-001",
    "gemini-embedding-2-preview",
    "text-embedding-005",
    "text-embedding-004",
]

FALLBACK_GEN_MODEL = "gemini-3.6-flash"
FALLBACK_EMBED_MODEL = "gemini-embedding-001"

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class ModelCatalog:
    available: list[str] = field(default_factory=list)
    generation: list[str] = field(default_factory=list)
    embedding: list[str] = field(default_factory=list)
    fetched_at: float = 0.0
    error: str | None = None


_cache: dict[str, ModelCatalog] = {}
_TTL = 600.0  # 10 分钟


def list_models(api_key: str) -> ModelCatalog:
    """列出当前 Key 可用的模型（带缓存）。"""
    if not api_key:
        return ModelCatalog(error="缺少 API Key")
    cached = _cache.get(api_key)
    if cached and (time.time() - cached.fetched_at) < _TTL:
        return cached

    catalog = ModelCatalog()
    try:
        resp = requests.get(f"{API_ROOT}/models", params={"key": api_key}, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("models", []):
            name = str(item.get("name", "")).replace("models/", "")
            if not name:
                continue
            catalog.available.append(name)
            methods = set(item.get("supportedGenerationMethods") or [])
            if "generateContent" in methods:
                catalog.generation.append(name)
            if methods & {"embedContent", "batchEmbedContents"}:
                catalog.embedding.append(name)
    except Exception as exc:  # noqa: BLE001
        catalog.error = str(exc)

    catalog.fetched_at = time.time()
    _cache[api_key] = catalog
    return catalog


def _pick(preferred: list[str], available: list[str]) -> str | None:
    if not available:
        return None
    for name in preferred:
        if name in available:
            return name
    # 退而求其次：找一个带 flash 字样的、版本号最大的
    flashes = [n for n in available if "flash" in n.lower() and "lite" not in n.lower()]
    if flashes:
        return sorted(flashes, key=_version_key)[-1]
    return sorted(available, key=_version_key)[-1]


def _version_key(name: str) -> tuple:
    parts = name.replace("preview", "").split("-")
    nums = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def resolve_generation_model(api_key: str | None = None, explicit: str | None = None) -> str:
    """确定用于"理解"的生成模型。"""
    explicit = (explicit or config.GEMINI_MODEL or "").strip()
    if explicit:
        return explicit.replace("models/", "")
    catalog = list_models(api_key or config.GEMINI_API_KEY)
    return _pick(PREFERRED_GEN_MODELS, catalog.generation) or FALLBACK_GEN_MODEL


def resolve_embedding_model(api_key: str | None = None, explicit: str | None = None) -> str:
    """确定用于"向量化"的向量模型。"""
    explicit = (explicit or config.GEMINI_EMBED_MODEL or "").strip()
    if explicit:
        return explicit.replace("models/", "")
    catalog = list_models(api_key or config.GEMINI_API_KEY)
    return _pick(PREFERRED_EMBED_MODELS, catalog.embedding) or FALLBACK_EMBED_MODEL


def candidate_generation_models(api_key: str | None = None, preferred: str | None = None,
                                limit: int = 5) -> list[str]:
    """返回可用的生成模型候选列表（按优先级）。

    免费档配额按模型计，所以当某个模型配额耗尽时，可以换下一个模型继续跑。
    """
    api_key = api_key or config.GEMINI_API_KEY
    catalog = list_models(api_key)
    available = catalog.generation
    ordered: list[str] = []
    if preferred:
        ordered.append(preferred)
    for name in PREFERRED_GEN_MODELS:
        if name in available and name not in ordered:
            ordered.append(name)
    # 其它 Flash / Flash-Lite 系列（各模型配额独立）
    extras = [
        n for n in available
        if "flash" in n.lower()
        and "preview" not in n
        and not any(k in n for k in ("tts", "live", "image", "native-audio"))
    ]
    for name in sorted(extras, key=_version_key, reverse=True):
        if name not in ordered:
            ordered.append(name)
    return ordered[:limit]


def catalog_snapshot(api_key: str | None = None) -> dict:
    """给 /api/health 用的模型概览。"""
    api_key = api_key or config.GEMINI_API_KEY
    if not api_key:
        return {
            "generation_model": None,
            "embedding_model": None,
            "available": [],
            "error": "未配置 GEMINI_API_KEY（离线模式）",
        }
    catalog = list_models(api_key)
    return {
        "generation_model": resolve_generation_model(api_key),
        "embedding_model": resolve_embedding_model(api_key),
        "generation_available": sorted(catalog.generation),
        "embedding_available": sorted(catalog.embedding),
        "available": sorted(catalog.available)[:40],
        "error": catalog.error,
    }
