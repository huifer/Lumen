"""理解结果缓存（落盘）。

为什么必须有：Gemini 免费档每个模型每天只有 ~20 次 generate_content 请求。
没有缓存的话，每次重建索引都要重新烧配额；有了缓存，文件没变就直接复用。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import config


def _file_key(path: str, mtime: float, size: int) -> str:
    """缓存键只看文件本身（路径 + 修改时间 + 大小）。

    不把模型写进键：换模型重建时也能复用旧结果——免费档配额宝贵，
    同一份文件没必要重新烧一次 API。
    """
    raw = f"{path}|{int(mtime)}|{size}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


class UnderstandCache:
    def __init__(self, path: Path | None = None):
        self.path = path or config.CACHE_FILE
        self.data: dict[str, dict] = {}
        self._dirty = False
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.data = {}

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        self._dirty = False

    def get(self, rec, model: str) -> dict | None:
        entry = self.data.get(_file_key(rec.path, rec.mtime, rec.size))
        if not entry:
            return None
        return {
            "description": entry.get("description", ""),
            "tags": entry.get("tags", []),
            "ocr_text": entry.get("ocr_text", ""),
        }

    def put(self, rec, model: str, result: dict) -> None:
        key = _file_key(rec.path, rec.mtime, rec.size)
        self.data[key] = {
            "path": rec.path,
            "model": model,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "description": result.get("description", ""),
            "tags": result.get("tags", []),
            "ocr_text": result.get("ocr_text", ""),
        }
        self._dirty = True

    def __len__(self) -> int:
        return len(self.data)
