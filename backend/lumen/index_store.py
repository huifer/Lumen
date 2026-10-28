"""索引持久化：记录(JSON) + 向量(npy) + IDF 状态，落到 data/ 目录。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import config
from .ingest import FileRecord


class IndexStore:
    def __init__(self, index_file: Path | None = None, vector_file: Path | None = None,
                 idf_file: Path | None = None):
        self.index_file = index_file or config.INDEX_FILE
        self.vector_file = vector_file or config.VECTOR_FILE
        self.idf_file = idf_file or config.IDF_FILE
        self.records: list[FileRecord] = []
        self.vectors: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.meta: dict = {"backend": "offline", "root": "", "embedder": {}}

    # ------------------------------------------------------------------ #
    def add(self, rec: FileRecord, vec: np.ndarray) -> None:
        self.records.append(rec)
        self.vectors = np.vstack([self.vectors, vec]) if len(self.records) > 1 else vec.reshape(1, -1)

    def save(self) -> None:
        for path in (self.index_file, self.vector_file, self.idf_file):
            path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": self.meta,
            "records": [r.to_dict() for r in self.records],
        }
        self.index_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        np.save(self.vector_file, self.vectors.astype(np.float32))
        self.idf_file.write_text(json.dumps(self.meta.get("embedder", {}), ensure_ascii=False), encoding="utf-8")

    def load(self) -> bool:
        if not self.index_file.exists() or not self.vector_file.exists():
            return False
        payload = json.loads(self.index_file.read_text(encoding="utf-8"))
        self.meta = payload.get("meta", {})
        self.records = [FileRecord(**r) for r in payload.get("records", [])]
        vectors = np.load(self.vector_file)
        self.vectors = vectors if len(self.records) == len(vectors) else np.zeros((0, 0), dtype=np.float32)
        return len(self.records) > 0

    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        self.records = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.meta = {"backend": "offline", "root": "", "embedder": {}}
        for path in (self.index_file, self.vector_file, self.idf_file):
            path.unlink(missing_ok=True)

    def __len__(self) -> int:
        return len(self.records)
