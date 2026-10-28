"""Step 2 · 多模态理解：用 LangChain + Gemini 在线理解图片与文档。

- GeminiUnderstander：图片 → 描述 + 标签 + OCR；文档 → 摘要 + 关键词（均走结构化输出）
- OfflineUnderstander：离线兜底（仅当显式 backend=offline 或 Gemini 彻底失败时）
"""
from __future__ import annotations

import base64
import io
import logging
import re
import time
from pathlib import Path

from . import config
from .ingest import FileRecord, color_name
from .models import resolve_generation_model
from .pipeline_utils import redact

logger = logging.getLogger("lumen.understand")

IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "ocr_text": {"type": "string"},
    },
    "required": ["description", "tags"],
}
DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "keywords"],
}

# 强制中文输出（Gemini 3.x 默认会飘到英文）
SYSTEM_PROMPT = (
    "你是一个中文多模态助手。所有 description / tags / summary / keywords / ocr_text "
    "必须使用简体中文输出；不要输出任何额外说明。"
)


class Understander:
    name = "base"

    def understand(self, rec: FileRecord) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# 在线理解（LangChain + Gemini）
# --------------------------------------------------------------------------- #
class GeminiUnderstander(Understander):
    """LangChain + Gemini 多模态理解。

    免费档配额是 **按模型** 计的（每个模型每天 ~20 次 generate 请求），
    所以这里支持“配额耗尽就换一个模型接着跑”。
    """

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 candidates: list[str] | None = None, cache=None):
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise RuntimeError("缺少 GEMINI_API_KEY，无法使用 Gemini 后端")
        self.candidates = [m for m in (candidates or []) if m]
        if model:
            self.candidates.insert(0, model)
        self.model = self.candidates[0] if self.candidates else resolve_generation_model(self.api_key)
        self.cache = cache
        self.quota_exhausted: set[str] = set()
        self.used_models: dict[str, int] = {}
        self._llms: dict[str, object] = {}

    # ---- LLM 工厂 ---------------------------------------------------------
    def _llm_for(self, model: str):
        if model not in self._llms:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._llms[model] = ChatGoogleGenerativeAI(model=model, google_api_key=self.api_key)
        return self._llms[model]

    def understand(self, rec: FileRecord) -> dict:
        # 1) 先看缓存（免费档配额紧张，必须缓存）
        if self.cache is not None:
            cached = self.cache.get(rec, self.model)
            if cached:
                return cached

        last_error: Exception | None = None
        for model in self.candidates:
            if model in self.quota_exhausted:
                continue
            try:
                result = self._understand_with(rec, model)
                self.model = model
                self.used_models[model] = self.used_models.get(model, 0) + 1
                if self.cache is not None:
                    self.cache.put(rec, model, result)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if is_quota_error(exc):
                    # 配额耗尽：换下一个模型（配额按模型计）
                    logger.warning("模型 %s 配额耗尽，自动切换下一个模型", model)
                    self.quota_exhausted.add(model)
                    continue
                logger.warning("Gemini 理解失败 %s (%s): %s", rec.name, model, redact(str(exc))[:200])
                break

        fallback = OfflineUnderstander().understand(rec)
        fallback["description"] += "（Gemini 调用失败，已回退离线理解）"
        logger.warning("Gemini 最终失败，回退离线: %s", redact(str(last_error or "")[:200]))
        return fallback

    def _understand_with(self, rec: FileRecord, model: str) -> dict:
        llm = self._llm_for(model)
        if rec.kind == "image":
            return self._image(llm, rec, model)
        return self._document(llm, rec, model)

    def _retry(self, fn, model: str, attempts: int = 3, base_delay: float = 1.5):
        """只重试瞬时错误（SSL/超时/5xx）；配额错误直接抛出让上层换模型。"""
        last: Exception | None = None
        for i in range(attempts):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last = exc
                if is_quota_error(exc):
                    raise
                if i < attempts - 1:
                    time.sleep(base_delay * (i + 1))
        raise last or RuntimeError("Gemini 调用失败")

    def _image(self, llm, rec: FileRecord, model: str) -> dict:
        b64 = image_as_jpeg_base64(rec.path)
        from langchain_core.messages import HumanMessage, SystemMessage

        msg = HumanMessage(
            content=[
                # LangChain 的 OpenAI 兼容图片格式：{"type":"image_url","image_url":{"url":...}}
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {
                    "type": "text",
                    "text": "描述这张图片，输出 JSON：description（中文一句话描述）、"
                    "tags（3-6 个中文标签数组）、ocr_text（图片里的文字，没有就空字符串）。",
                },
            ]
        )
        out = self._retry(
            lambda: llm.with_structured_output(IMAGE_SCHEMA).invoke(
                [SystemMessage(content=SYSTEM_PROMPT), msg]
            ),
            model,
        )
        tags = [str(t) for t in (out.get("tags") or [])]
        if rec.dominant_color_name:
            tags.append(rec.dominant_color_name)
        return {
            "description": str(out.get("description") or rec.title),
            "tags": dedupe(tags)[:8],
            "ocr_text": str(out.get("ocr_text") or ""),
        }

    def _document(self, llm, rec: FileRecord, model: str) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage

        body = (rec.text or "")[:6000]
        prompt = (
            "总结下面的文档，输出 JSON：summary（两句话中文摘要）、"
            "keywords（3-6 个关键词数组）。\n\n"
            f"文档标题：{rec.title}\n正文：\n{body}"
        )
        out = self._retry(
            lambda: llm.with_structured_output(DOC_SCHEMA).invoke(
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
            ),
            model,
        )
        summary = str(out.get("summary") or first_sentences(body, 2))
        keywords = [str(k) for k in (out.get("keywords") or [])]
        return {
            "description": f"文档《{rec.title}》：{summary}",
            "tags": dedupe(keywords + [rec.ext.lstrip(".")])[:8],
            "ocr_text": "",
        }


# --------------------------------------------------------------------------- #
# 离线理解（兜底）
# --------------------------------------------------------------------------- #
class OfflineUnderstander(Understander):
    name = "offline"

    def understand(self, rec: FileRecord) -> dict:
        if rec.kind == "image":
            return self._image(rec)
        if rec.kind in {"text", "doc", "pdf"}:
            return self._document(rec)
        return {"description": f"文件 {rec.name}", "tags": [rec.ext.lstrip(".")], "ocr_text": ""}

    def _image(self, rec: FileRecord) -> dict:
        color = rec.dominant_color_name or "未知"
        size_txt = f"{rec.width}×{rec.height}" if rec.width else "未知尺寸"
        kind_txt = "UI 界面截图" if rec.is_screenshot else "图片/照片"
        parts = [f"一张{kind_txt}", f"尺寸 {size_txt}", f"主色调为{color}"]
        if rec.dominant_ratio:
            parts.append(f"{color}占比约 {rec.dominant_ratio}%")
        description = "，".join(parts) + "。"

        tags = [color, "截图" if rec.is_screenshot else "图片"]
        if rec.dominant:
            tags.append(rec.dominant)
        tags.extend(re.findall(r"[A-Za-z]{3,}", rec.name)[:3])

        ocr_text = run_ocr(rec.path)
        if ocr_text:
            description += f" 图中文字包含：{ocr_text[:40]}。"
            tags.extend([w for w in re.findall(r"[A-Za-z]{3,}", ocr_text)[:3]])

        return {"description": description, "tags": dedupe(tags)[:8], "ocr_text": ocr_text}

    def _document(self, rec: FileRecord) -> dict:
        body = rec.text or ""
        summary = first_sentences(body, 2) or rec.title
        keywords = extract_keywords(body, 6)
        description = f"文档《{rec.title}》：{summary}"
        tags = dedupe(keywords + [rec.ext.lstrip("."), "文档"])
        return {"description": description, "tags": tags[:8], "ocr_text": ""}


# --------------------------------------------------------------------------- #
# 工厂 & 工具
# --------------------------------------------------------------------------- #
def get_understander(backend: str | None = None, model: str | None = None,
                     candidates: list[str] | None = None, cache=None) -> Understander:
    backend = (backend or config.DEFAULT_BACKEND).lower()
    if backend == "gemini" and config.GEMINI_API_KEY:
        try:
            return GeminiUnderstander(model=model, candidates=candidates, cache=cache)
        except Exception:
            return OfflineUnderstander()
    return OfflineUnderstander()


def is_quota_error(exc: Exception) -> bool:
    """判断是不是配额/限流错误（这类错误重试没用，要换模型）。"""
    text = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in text or "429" in text or "QUOTA" in text


def run_ocr(image_path: str, timeout: int = 20) -> str:
    """调用 tesseract CLI 做 OCR，失败静默返回空串。"""
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            out_base = tmp.name
        out_file = Path(out_base + ".txt")
        try:
            subprocess.run(
                [TESSERACT_BIN, image_path, out_base, "-l", OCR_LANGS],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            text = out_file.read_text(encoding="utf-8", errors="ignore").strip() if out_file.exists() else ""
        finally:
            Path(out_base).unlink(missing_ok=True)
            out_file.unlink(missing_ok=True)
        return re.sub(r"\s+", " ", text)[:1000]
    except Exception:
        return ""


def first_sentences(text: str, n: int = 2) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[。！？.!?;；])", text)
    return "".join(p for p in parts[:n] if p.strip()).strip()[:200]


def extract_keywords(text: str, top_n: int = 6) -> list[str]:
    """中英简易关键词：英文按词，中文按 2-gram 词频。"""
    text = text.lower()
    words = re.findall(r"[a-z][a-z0-9]{2,}", text)
    cjk = re.findall(r"[一-鿿]+", text)
    grams: list[str] = []
    for run in cjk:
        if len(run) == 1:
            grams.append(run)
        for i in range(len(run) - 1):
            grams.append(run[i : i + 2])
    counts: dict[str, int] = {}
    for token in words + grams:
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top_n]]


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def image_as_jpeg_base64(image_path: str) -> str:
    """统一转成 JPEG 再上传，避免 bmp/tiff 等格式不被 Gemini 接受。"""
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode()


# tesseract 相关（离线 OCR 用）
TESSERACT_BIN = config.TESSERACT_BIN if hasattr(config, "TESSERACT_BIN") else "tesseract"
OCR_LANGS = config.OCR_LANGS if hasattr(config, "OCR_LANGS") else "chi_sim+eng"
