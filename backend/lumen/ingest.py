"""Step 1 · 文件采集：扫描目录，给每个文件建一份"档案"。

只做本地 IO，不联网；坏文件 try/except 跳过，不中断整批扫描。
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageFile

from . import config

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = 120_000_000


@dataclass
class FileRecord:
    path: str
    rel_path: str
    name: str
    ext: str
    kind: str          # image / pdf / doc / text / other
    size: int
    mtime: float
    width: int | None = None
    height: int | None = None
    dominant: str | None = None          # "#rrggbb"
    dominant_color_name: str | None = None
    dominant_ratio: float | None = None
    is_screenshot: bool = False
    text: str = ""                      # 文本类文件的正文片段
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    ocr_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# 类型识别与元数据
# --------------------------------------------------------------------------- #
def detect_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in config.IMAGE_EXT:
        return "image"
    if ext in config.PDF_EXT:
        return "pdf"
    if ext in config.DOC_EXT:
        return "doc"
    if ext in config.TEXT_EXT:
        return "text"
    return "other"


def extract_meta(path: Path) -> dict:
    """抽取尺寸 / 主色 / 文本片段等元数据。"""
    meta: dict = {}
    stat = path.stat()
    meta["size"] = stat.st_size
    meta["mtime"] = stat.st_mtime

    ext = path.suffix.lower()
    if ext in config.IMAGE_EXT:
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                meta["width"], meta["height"] = img.size
                color, ratio = dominant_color(img)
                meta["dominant"] = color
                meta["dominant_color_name"] = color_name(color)
                meta["dominant_ratio"] = ratio
                meta["is_screenshot"] = is_ui_screenshot(img)
        except Exception:
            pass
    elif ext in config.TEXT_EXT:
        try:
            meta["text"] = path.read_text(encoding="utf-8", errors="ignore")[:8000]
        except Exception:
            meta["text"] = ""
    elif ext in config.DOC_EXT:
        meta["text"] = extract_ooxml_text(path)[:8000]
    return meta


def extract_ooxml_text(path: Path) -> str:
    """从 docx/pptx/xlsx（OOXML zip）里抠出纯文本，免装额外依赖。"""
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.endswith(".xml")]
            if path.suffix.lower() == ".docx":
                names = [n for n in names if "document.xml" in n]
            elif path.suffix.lower() == ".pptx":
                names = [n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]
            elif path.suffix.lower() == ".xlsx":
                names = [n for n in names if "sharedStrings" in n]
            chunks: list[str] = []
            for name in sorted(names):
                xml = zf.read(name).decode("utf-8", errors="ignore")
                chunks.extend(re.findall(r"<a:t>(.*?)</a:t>|<w:t[^>]*>(.*?)</w:t>|<t[^>]*>(.*?)</t>", xml, re.S))
            flat = [a or b or c for a, b, c in chunks]
            return "\n".join(t for t in flat if t)
    except Exception:
        return ""


def dominant_color(img: Image.Image, colors: int = 6) -> tuple[str, float]:
    """量化取主色，返回 (hex, 占比)。"""
    small = img.copy()
    small.thumbnail((160, 160))
    quant = small.quantize(colors=colors, method=Image.MEDIANCUT).convert("RGB")
    pixels = list(quant.getdata())
    if not pixels:
        return "#808080", 0.0
    counts: dict[tuple[int, int, int], int] = {}
    for px in pixels:
        counts[px] = counts.get(px, 0) + 1
    (r, g, b), count = max(counts.items(), key=lambda kv: kv[1])
    ratio = count / len(pixels)
    return f"#{r:02x}{g:02x}{b:02x}", round(ratio * 100, 1)


def is_ui_screenshot(img: Image.Image) -> bool:
    """启发式判定 UI 截图：宽屏比例 + 大量水平/垂直直边（界面色块与边框）。

    照片/渐变图几乎没有直边，所以用“直线边缘密度”区分。
    """
    w, h = img.size
    if w == 0 or h == 0:
        return False
    if not (1.2 <= w / h <= 2.6):
        return False

    try:
        import numpy as np

        gray = img.convert("L")
        gray.thumbnail((160, 160))
        arr = np.asarray(gray, dtype=np.int16)
        if arr.shape[0] < 8 or arr.shape[1] < 8:
            return False
        dx = np.abs(np.diff(arr, axis=1)) > 24
        dy = np.abs(np.diff(arr, axis=0)) > 24
        edge_rows = int((dx.sum(axis=1) > 0.03 * dx.shape[1]).sum())
        edge_cols = int((dy.sum(axis=0) > 0.03 * dy.shape[0]).sum())
        return edge_rows >= 10 and edge_cols >= 40
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 颜色命名（HSL 分桶，给搜索一点"人话"）
# --------------------------------------------------------------------------- #
COLOR_NAMES = [
    ("红", 345, 360), ("橙", 15, 45), ("黄", 45, 70), ("绿", 70, 165),
    ("青", 165, 200), ("蓝", 200, 255), ("紫", 255, 300), ("粉", 300, 345),
]


def color_name(hex_color: str) -> str:
    try:
        r = int(hex_color[1:3], 16) / 255
        g = int(hex_color[3:5], 16) / 255
        b = int(hex_color[5:7], 16) / 255
    except Exception:
        return "未知"
    maxc, minc = max(r, g, b), min(r, g, b)
    v, s = maxc, 0.0 if maxc == 0 else (maxc - minc) / maxc
    if s < 0.12:
        return "黑" if v < 0.25 else ("白" if v > 0.85 else "灰")
    d = maxc - minc
    if maxc == r:
        h = 60 * (((g - b) / d) % 6)
    elif maxc == g:
        h = 60 * ((b - r) / d + 2)
    else:
        h = 60 * ((r - g) / d + 4)
    for name, lo, hi in COLOR_NAMES:
        if lo <= h < hi:
            return name
    return "彩色"


# --------------------------------------------------------------------------- #
# 扫描
# --------------------------------------------------------------------------- #
def scan(root: str | Path, limit: int = 2000) -> list[FileRecord]:
    """递归扫描目录，返回文件档案列表。"""
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"目录不存在: {root_path}")

    records: list[FileRecord] = []
    for path in sorted(root_path.rglob("*")):
        if len(records) >= limit:
            break
        if not path.is_file():
            continue
        if any(part in config.SKIP_DIRS or part.startswith(".") for part in path.relative_to(root_path).parts[:-1]):
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in (config.IMAGE_EXT | config.PDF_EXT | config.DOC_EXT | config.TEXT_EXT):
            continue
        try:
            kind = detect_type(path)
            meta = extract_meta(path)
        except Exception:
            continue
        record = FileRecord(
            path=str(path),
            rel_path=str(path.relative_to(root_path)),
            name=path.name,
            ext=path.suffix.lower(),
            kind=kind,
            title=path.stem.replace("_", " ").replace("-", " ").strip(),
            **meta,
        )
        records.append(record)
    return records


def file_datetime(record: FileRecord) -> str:
    return datetime.fromtimestamp(record.mtime).strftime("%Y-%m-%d %H:%M")
