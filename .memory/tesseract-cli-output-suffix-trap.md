---
name: tesseract-cli-output-suffix-trap
description: tesseract CLI 输出到 `<out_base>.txt`（自动加后缀），读错路径会静默得到空 OCR 文本
type: gotcha
---

# tesseract CLI 的输出文件会自动加 `.txt` 后缀

## Why

`tesseract input.png /tmp/abc` 生成的是 `/tmp/abc.txt`，不是 `/tmp/abc`。
如果代码把 `out_base` 直接当结果文件读，会得到空字符串——而 `subprocess.run(check=True)` 依然成功，
所以 OCR 静默失效，没有任何报错（表现为"图片搜不到文字"）。

## How to apply

- 用 `tesseract <img> <out_base>` 时，结果文件是 `<out_base>.txt`；读取与清理都要按 `.txt` 处理。
- OCR 调用整体包 try/except + 超时（tesseract 对大图可能很慢）。
- 本机 homebrew tesseract 自带 `chi_sim`/`eng`/`osd`/`snum` 语言包（`/opt/homebrew/share/tessdata`），
  中文 OCR 直接用 `-l chi_sim+eng`。
- 自检方式：`tesseract img.png stdout -l chi_sim+eng` 先在命令行验证。

## Related

- [[gdg-dev-lumen-demo]]
