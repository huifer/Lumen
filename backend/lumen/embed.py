"""Step 3 · 向量化：把"理解结果"变成可检索的数字。

- OfflineEmbedder：hashing trick + IDF 的 TF-IDF（中英免分词，纯本地）
- GeminiEmbedder：Gemini text-embedding-004
两者输出统一为 L2 归一化的稠密向量（numpy）。
"""
from __future__ import annotations

import math
import re

import numpy as np

from . import config
from .models import resolve_embedding_model

DIM = 2048
CJK_RE = re.compile(r"[一-鿿]")
WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """中文按 2-gram、英文按词切分。"""
    text = (text or "").lower()
    tokens: list[str] = []
    tokens.extend(WORD_RE.findall(text))
    for run in re.findall(r"[一-鿿]+", text):
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            tokens.append(run[i : i + 2])
    return tokens


def hash_bucket(token: str) -> int:
    h = 2166136261
    for ch in token.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h % DIM


class OfflineEmbedder:
    """哈希 TF-IDF：不需要词典、不需要分词器、中英文都能跑。"""

    name = "offline"

    def __init__(self, dim: int = DIM):
        self.dim = dim
        self.idf: dict[int, float] = {}

    def fit(self, texts: list[str]) -> "OfflineEmbedder":
        df: dict[int, int] = {}
        for text in texts:
            for bucket in {hash_bucket(t) for t in tokenize(text)}:
                df[bucket] = df.get(bucket, 0) + 1
        total = max(1, len(texts))
        self.idf = {b: math.log((total + 1) / (c + 1)) + 1.0 for b, c in df.items()}
        return self

    def transform(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        counts: dict[int, int] = {}
        for token in tokenize(text):
            bucket = hash_bucket(token)
            counts[bucket] = counts.get(bucket, 0) + 1
        for bucket, count in counts.items():
            vec[bucket] = (1.0 + math.log(count)) * self.idf.get(bucket, 1.0)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    def transform_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self.transform(t) for t in texts])

    def state_dict(self) -> dict:
        return {"dim": self.dim, "idf": {str(k): v for k, v in self.idf.items()}}

    @classmethod
    def from_state(cls, state: dict) -> "OfflineEmbedder":
        obj = cls(dim=int(state.get("dim", DIM)))
        obj.idf = {int(k): float(v) for k, v in state.get("idf", {}).items()}
        return obj


class GeminiEmbedder:
    """Gemini 向量模型（gemini-embedding-001 / gemini-embedding-2-preview …），
    用 LangChain 的 GoogleGenerativeAIEmbeddings。
    """

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, dim: int | None = None):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise RuntimeError("缺少 GEMINI_API_KEY，无法使用 Gemini 向量化")
        self.model = (model or "").strip() or resolve_embedding_model(self.api_key)
        self.dim = dim or config.EMBED_DIM
        self._embedder = GoogleGenerativeAIEmbeddings(
            model=f"models/{self.model}",
            google_api_key=self.api_key,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.dim,
        )

    def fit(self, texts: list[str]) -> "GeminiEmbedder":
        return self

    def transform(self, text: str) -> np.ndarray:
        vec = self._embedder.embed_query(text)
        arr = np.asarray(vec, dtype=np.float32)
        norm = float(np.linalg.norm(arr)) or 1.0
        return arr / norm

    def transform_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = self._embedder.embed_documents(texts)
        arr = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def state_dict(self) -> dict:
        return {"model": self.model, "dim": self.dim}


def get_embedder(backend: str | None = None, model: str | None = None):
    backend = (backend or config.DEFAULT_BACKEND).lower()
    if backend == "gemini" and config.GEMINI_API_KEY:
        try:
            return GeminiEmbedder(model=model)
        except Exception:
            return OfflineEmbedder()
    return OfflineEmbedder()
