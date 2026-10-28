"""全局配置：路径、环境变量、后端选择。"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
THUMB_DIR = DATA_DIR / "thumbs"
SAMPLE_DIR = BACKEND_DIR / "sample_data"

INDEX_FILE = DATA_DIR / "index.json"
VECTOR_FILE = DATA_DIR / "vectors.npy"
IDF_FILE = DATA_DIR / "idf.json"
CACHE_FILE = DATA_DIR / "understand_cache.json"


def load_dotenv(path: Path | None = None) -> None:
    """极简 .env 加载（不引入额外依赖）。"""
    path = path or (BACKEND_DIR / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# 模型 ID 迭代很快，留空则运行时自动发现当前 Key 可用的最新模型（见 models.py）
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2").strip()
# 向量维度（gemini-embedding-001 支持 768/1536/3072；text-embedding-004 仅 768）
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))

# OCR / tesseract
TESSERACT_BIN = os.getenv("TESSERACT_BIN", "tesseract")
OCR_LANGS = os.getenv("OCR_LANGS", "chi_sim+eng")

# 没有 Key 就自动降级到离线模式
DEFAULT_BACKEND = "gemini" if GEMINI_API_KEY else "offline"

DEFAULT_SCAN_ROOT = str(SAMPLE_DIR)

# 扫描时跳过的目录名
SKIP_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "Library", "System", "Applications", ".cache", "dist", "build", ".next",
}

# 允许扫描的扩展名
TEXT_EXT = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".yaml", ".yml", ".py", ".html"}
DOC_EXT = {".docx", ".pptx", ".xlsx"}
PDF_EXT = {".pdf"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
