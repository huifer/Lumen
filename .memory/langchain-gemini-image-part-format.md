---
name: langchain-gemini-image-part-format
description: langchain-google-genai 传图片必须用 {"type":"image_url","image_url":{"url":data:...}} 嵌套格式，写成扁平的 {"type":"image_url","url":...} 会 KeyError
type: gotcha
---

# LangChain 传图给 Gemini 的正确 content 格式

## Why

`langchain-google-genai` 4.x 里，图片 part 走 OpenAI 兼容分支：

```python
elif part["type"] == "image_url":
    img_url = part["image_url"]          # ← 取的是 "image_url" 这个 key
    if isinstance(img_url, dict):
        if "url" not in img_url: raise ValueError(...)
        img_url = img_url["url"]
```

所以必须嵌套：

```python
{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
```

写成扁平的 `{"type": "image_url", "url": ...}` 会直接 `KeyError: 'image_url'`。

## How to apply

- 另一个可用格式是 `media` 类型：`{"type": "media", "mime_type": "image/jpeg", "data": <bytes>}`（可带 `media_resolution`）。
- Gemini 3.x 支持 per-part `media_resolution`（`{"level": ...}`），2.5 及更早会警告并忽略。
- `with_structured_output(dict_schema)` 可用；Gemini 3.x 固定采样参数，传 `temperature` 会警告
  "uses fixed sampling defaults; the sampling parameter(s) temperature will be ignored" —— 干脆别传。
- Gemini 3.x 默认会飘英文：加一条 SystemMessage 强制"必须用简体中文输出"即可。

## Related

- [[gemini-free-tier-quota-per-model]]
- [[gdg-dev-lumen-demo]]
