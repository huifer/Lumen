---
name: chrome-devtools-mcp-blocked-by-running-browser
description: chrome-devtools MCP 连不上时（已有 Chrome 占用 profile），改用 headless Chrome CLI --screenshot 验证页面
type: workaround
---

# chrome-devtools MCP 被已运行的 Chrome 占用时的替代验证法

## Why

调用 `mcp({server:"chrome-devtools"})` 后 `new_page` / `list_pages` 报
"The browser is already running for ~/.cache/chrome-devtools-mcp/chrome-profile"——
该 MCP 只有一个固定 profile，本机已有 Chrome 实例在跑时连不上，所有交互式验证都做不了。

## How to apply

改用系统 Chrome 的 headless 模式截图（macOS 路径：
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`）：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-first-run \
  --user-data-dir=/tmp/chrome-shot \
  --window-size=1280,1500 --virtual-time-budget=10000 \
  --screenshot=/tmp/shot.png "http://127.0.0.1:3000/?q=xxx"
```

- 用独立 `--user-data-dir` 避免与已运行的实例冲突。
- headless 不会点击，所以给被测页面加上 URL 参数直出结果（如 `?q=` 预填搜索）再截图，效果等同交互验证。
- 截图后用 read 工具直接看图，能检查布局/样式/数据是否正确。

## Related

- [[gdg-dev-lumen-demo]]
