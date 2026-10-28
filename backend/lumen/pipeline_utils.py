"""小工具：异常脱敏（异常信息里可能带 API Key）。"""
from __future__ import annotations

from . import config


def redact(text: str) -> str:
    """抹掉可能出现在异常信息里的 API Key。"""
    key = config.GEMINI_API_KEY
    if key and key in (text or ""):
        return text.replace(key, "***")
    return text or ""
