# Lumen User Manual (Beginner Edition)

> This manual assumes you have **never written a line of code**. Just follow along and copy-paste, step by step — every step tells you what you **should see**.
> The whole walkthrough takes about **15 minutes** (not counting download/install time).
>
> Note on UI language: the app defaults to Chinese, but there is an **EN** button at the top of the page (or add `?lang=en` to the URL) to switch the interface to English. This manual quotes the default Chinese labels in 「」 with English translations so you can match them on screen either way.

---

## Table of Contents

1. [What Is This Thing](#1-what-is-this-thing)
2. [One-Time Setup](#2-one-time-setup)
3. [Get a Free API Key (5 Minutes)](#3-get-a-free-api-key-5-minutes)
4. [Start the System (3 Commands)](#4-start-the-system-3-commands)
5. [Using It (Indexing and Search)](#5-using-it-indexing-and-search)
6. [Searching Your Own Files](#6-searching-your-own-files)
7. [Troubleshooting (Fix by Symptom)](#7-troubleshooting-fix-by-symptom)
8. [How to Shut Down](#8-how-to-shut-down)
9. [Mini Glossary](#9-mini-glossary)

---

## 1. What Is This Thing

In one sentence: **find the images and documents on your computer by describing them in a sentence.**

For example, type 「红色背景的产品截图」 ("a product screenshot on a red background") and it will find the matching images, complete with thumbnails, AI-written descriptions, file paths, and similarity scores.

Its two defining traits:

| Trait | What it means |
| --- | --- |
| **Runs locally** | Your files are never uploaded anywhere. The AI only receives "understanding results", never the files themselves (images are sent to Google's Gemini for analysis, but only when you have configured a Key and clicked 「构建索引」 (Build Index)) |
| **Works with or without a Key** | With a free Gemini Key → the AI writes high-quality Chinese descriptions for each file (recommended); without a Key → search still works, just with "shallower" descriptions (color, dimensions, and OCR only) |

It consists of two programs (both run on your computer):

- **Backend** (Python): the part that does the real work — scanning files, calling the AI, building the index, running searches
- **Frontend** (web page): the interface you see, opened in a browser

---

## 2. One-Time Setup

### 2.1 Install Two Programs

| Software | What it's for | Download | Version |
| --- | --- | --- | --- |
| **Python** | Runs the backend | https://www.python.org/downloads/ | 3.10 or newer |
| **Node.js** | Runs the frontend web UI | https://nodejs.org/ | 18 or newer (get the LTS version) |

Just keep clicking "Next" during installation. **macOS users**: check "Add to PATH" when installing Python (if the option appears).

### 2.2 Verify the Installation

Open a terminal:

- **macOS**: press `Command + Space`, type `终端` or `Terminal`, press Enter
- **Windows**: press the `Win` key, type `PowerShell` or `cmd`, press Enter

Type these two commands in the terminal (press Enter after each):

```bash
python3 --version
node --version
```

**You should see** output like this (the exact numbers don't matter):

```
Python 3.10.20
v24.15.0
```

✅ Both lines show version numbers → setup is done, go to Step 3.
❌ It says `command not found` → installation failed. Go back to 2.1 and reinstall, then **close and reopen the terminal** before trying again.

### 2.3 Unzip the Project

Unzip `lumen-demo.zip` into a folder whose path contains **no Chinese characters and no spaces**, for example:

- macOS: `~/lumen-demo` (that's Users/your-name/lumen-demo)
- Windows: `D:\lumen-demo`

Then enter that folder in the terminal (do this first every time before using the project):

```bash
cd ~/lumen-demo
```

> 💡 `cd` means "change into a folder". Wherever you unzipped, `cd` there.
> 💡 Can't find where you unzipped it? On macOS you can **drag the folder straight into the terminal window** and the path will appear automatically.

---

## 3. Get a Free API Key (5 Minutes)

> An API Key is a string of "pass" characters proving you're allowed to use Google's Gemini AI. For personal use it is **free**.

1. Open: **https://aistudio.google.com/apikey**
2. Sign in with your Google account (register one if you don't have it)
3. Click **「Create API key」**
4. A string of characters appears, starting with something like `AIzaSy...` or `AQ....` — **click the copy button next to it**

> ⚠️ This string is effectively a password. Don't post it in group chats, don't commit it to a code repository.

### 3.1 Put the Key into the Project

**Step 1**: create the config file inside the project (copy the template):

```bash
cd backend
cp .env.example .env
```

**Step 2**: open the file in a text editor:

- macOS: `open -e .env`
- Windows: `notepad .env`

**Step 3**: find this line, paste your Key after the `=`, then save and close:

```ini
GEMINI_API_KEY=paste the string you copied here
```

**It should look like** (example — your key will differ):

```ini
GEMINI_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Save and close, then go back to the project root:

```bash
cd ..
```

> ⚠️ Common mistakes:
> - **No spaces** on either side of the `=`
> - Don't add quotes
> - If you are in mainland China, you may need a proxy to open the website and call the API (see Problem 9 in Section 7)

---

## 4. Start the System (3 Commands)

### Option A: One command starts everything (recommended)

```bash
bash scripts/dev.sh
```

### Option B: Start them separately (two terminal windows; easier to read the logs)

**Terminal 1 — start the backend:**

```bash
bash scripts/start-backend.sh
```

**You should see** (the first run downloads dependencies automatically, which takes a few minutes — be patient):

```
→ 后端启动中: http://127.0.0.1:8000  (docs: /docs)
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> (The first line means "→ Backend starting at: http://127.0.0.1:8000, API docs at /docs".)

> 💡 The first run creates a virtual environment and installs dependencies automatically (i.e. downloads the tool packages) — just wait.
> 💡 On macOS, if you get `Permission denied`, first run: `chmod +x scripts/*.sh`, then run the script again.

**Terminal 2 — start the frontend** (click the "+" at the top of the terminal to open a new window; `cd` into the project folder first, same as before):

```bash
bash scripts/start-frontend.sh
```

**You should see**:

```
→ 前端启动中: http://127.0.0.1:3000
▲ Next.js 15.5.28
- Local: http://localhost:3000
✓ Ready in 2.1s
```

> (The first line means "→ Frontend starting at: http://127.0.0.1:3000".)

### 4.1 Open the Web UI

In a browser (Chrome/Safari, either is fine), visit:

**http://localhost:3000**

**You should see**: a dark-themed page titled 「Lumen 本地多模态文件检索」 ("Lumen Local Multimodal File Search"), with an 「索引目录」 ("Index Directory") input box and a blue 「搜索」 ("Search") button.

**How do you know the Key is working?** Look at the small status line on the page:

- ✅ It shows `后端 gemini · 已配置 Gemini Key` ("backend: gemini · Gemini Key configured") → success; you'll also see two dropdowns: 「生成模型 / 向量模型」 ("generation model / embedding model")
- ⚠️ It shows `后端 offline · 无 Key（离线模式）` ("backend: offline · no Key (offline mode)") → the Key wasn't picked up. Go back to 3.1 and check (90% of the time it's an unsaved `.env` or the backend wasn't restarted)

---

## 5. Using It (Indexing and Search)

> Think of the 「索引」 ("index") as a set of index cards: the system first looks at every file and writes a content card for it; searching afterwards is just flipping through the cards. That's why **you must build the index before searching**.

### Step 1: Build the index (required the first time)

1. The 「索引目录」 ("Index Directory") box is pre-filled with the bundled sample path — **leave it as is**
2. Under 「理解后端」 ("Understanding backend"), pick **Gemini** (if you configured a Key)
3. Leave the generation model / embedding model dropdowns on 「自动」 ("Auto")
4. Click the 「构建索引」 ("Build Index") button

**You should see**:

- The button changes to 「索引中…」 ("Indexing…")
- After roughly 30–60 seconds (for the 8 sample files), the status bar below shows:

```
● 后端 gemini · 已配置 Gemini Key | 已索引 8 个文件 | 本次索引 8 个文件 · 47268ms · 理解后端 gemini
```

> Translation: `backend: gemini · Gemini Key configured | 8 files indexed | indexed 8 files this run · 47268ms · understanding backend: gemini`

> 💡 **Why does it take this long?** Every file is sent to Gemini to be looked at. The good news: **results are saved**, so rebuilding the same files the second time is nearly instant (the page will show 「全部命中缓存，0 次模型调用」 — "all cache hits, 0 model calls").

### Step 2: Search

Type a query sentence into the search box and click 「搜索」 ("Search") (or just press Enter). Try these four examples (the page also has shortcut buttons for them):

| You type | Top result you should see |
| --- | --- |
| 「红色背景的产品截图」 ("red-background product screenshot") | 红色背景产品截图.png |
| 「含有发票的文档」 ("a document containing an invoice") | 发票说明.txt |
| 「海边日落照片」 ("seaside sunset photo") | 海边日落.png |
| 「合同金额」 ("contract amount") | 合同摘要.docx |

### Step 3: Reading a result card

Each card shows:

| Element | Meaning |
| --- | --- |
| **0.779** (circle in the top-right) | Similarity score; the closer to 1, the better the match |
| **Thumbnail / TXT·MD·DOCX badge** | Images show a thumbnail; documents show their type and a content preview |
| **Description** | The AI-written "content card" for this file |
| **Small tags** (sunset / seascape / invoice…) | Keywords assigned by the AI |
| **Path + size** | Where the file lives on your computer |
| **「打开原文件 ↗」 ("Open original file")** | Opens the original file in a new tab |

### Tips

- The **Top 6** control next to the search box sets the max number of results shown; you can change it to 4/8/12
- A search results page can be shared by **copying the browser URL**, e.g. `http://localhost:3000/?q=海边日落照片`
- The top-right corner shows how long this search took (e.g. `2079ms · gemini`)

---

## 6. Searching Your Own Files

To make the system search your own folders (e.g. your Downloads folder):

1. Change the path in the 「索引目录」 ("Index Directory") box to your folder:
   - macOS: `/Users/your-username/Downloads` (you can also **drag the folder straight into the input box**)
   - Windows: `C:\Users\your-username\Downloads`
2. Click 「构建索引」 ("Build Index") and wait for it to finish
3. Search as usual

### ⚠️ Read this before indexing a large folder

| Caution | Details |
| --- | --- |
| **Free quota is limited** | On the Gemini free tier, each model can "look at" only about **20 files per day**. If your folder has 100 images, only 20 get understood today; the rest resume tomorrow (or switch to another model to continue). Files already understood are remembered and won't consume quota twice |
| **Don't scan system directories** | Don't enter paths like `/`, `/System`, or `C:\Windows` — slow and error-prone. Only scan your own folders |
| **Supported file types** | Images: png / jpg / jpeg / gif / webp / bmp; documents: txt / md / csv / json / py / html / yaml / docx / pptx / xlsx; pdf: only the filename is recorded (content is not read) |
| **Time expectations** | Gemini mode: roughly 5–20 seconds per file; offline mode is much faster |

---

## 7. Troubleshooting (Fix by Symptom)

### Problem 1: The page shows 「连不上后端：...」 ("Cannot connect to backend: ...")

| Cause | Fix |
| --- | --- |
| The backend isn't running | Go back to Section 4 and start the backend in Terminal 1 first |
| The backend failed on startup | Read the red error text in Terminal 1 and match it against the other items in this section |

### Problem 2: The command fails with `Permission denied` (macOS)

```bash
chmod +x scripts/*.sh
```
Then run the startup script again.

### Problem 3: The command fails with `command not found: python3` / `node`

The software isn't installed properly, or you didn't reopen the terminal after installing. Reopen the terminal and try again; if it still fails, reinstall (Section 2.1).

### Problem 4: Port already taken: `address already in use` / `port 8000 in use`

A previous instance is still running. Shut it down first (Section 8), then start again; or start the backend on a different port:

```bash
cd backend
.venv/bin/python -m uvicorn lumen.server:app --port 8001
```

Then point the frontend at the new address (new terminal):

```bash
cd frontend
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001 npm run dev
```

### Problem 5: It shows 「无 Key（离线模式）」 ("no Key (offline mode)") even though you filled in the Key

Check in order:

1. Is the file in the right place? It must be **`backend/.env`** (not the project root, and not `.env.example`)
2. Is the content formatted correctly? `GEMINI_API_KEY=AIza...` (no spaces around `=`, no quotes)
3. **You must restart the backend after editing** (stop it with Ctrl+C, then run the startup script again) — this is the most common cause

### Problem 6: The status bar shows 「配额已满：gemini-3.6-flash」 ("Quota exhausted: gemini-3.6-flash")

The free tier allows about 20 calls per model per day, and they're used up. Three options:

1. **Do nothing**: the system automatically switches to another model and continues (the status bar shows which model is actually in use)
2. Manually switch models in the 「生成模型」 ("generation model") dropdown (e.g. `gemini-3.5-flash-lite`)
3. Rebuild the index tomorrow (quota resets daily); **already-processed files don't need reprocessing** (they're cached)

### Problem 7: A card's description ends with 「（Gemini 调用失败，已回退离线理解）」 ("Gemini call failed, fell back to offline understanding")

The Gemini call for that file hit a network error (e.g. your proxy dropped for a moment). **Just click 「构建索引」 ("Build Index") again** — thanks to caching, successful files won't consume quota twice; only the failed ones get retried.

### Problem 8: Search returns nothing / very few results

1. Confirm you clicked 「构建索引」 ("Build Index") and the status bar shows 「已索引 N 个文件」 ("N files indexed") with N > 0
2. Try rephrasing (e.g. 「发票」 "invoice" → 「含有发票的文档」 "a document containing an invoice")
3. The file type you want isn't supported (see the file-type table in Section 6)

### Problem 9: In mainland China, aistudio.google.com won't open, or indexing keeps failing

Gemini is a Google service; your network must be able to reach Google:

1. Turn on your proxy software (e.g. Clash)
2. Make the **terminal** use the proxy too (run this in the terminal where you start the backend, first):

   ```bash
   export https_proxy=http://127.0.0.1:7890
   export http_proxy=http://127.0.0.1:7890
   ```

   (`7890` is Clash's default port; substitute your own software's port)
   In Windows PowerShell use: `$env:HTTPS_PROXY="http://127.0.0.1:7890"`
3. Then run the startup script

### Problem 10: Images are found by their text content, but Chinese text isn't matched

Offline mode uses tesseract to read text in images, which needs the Chinese language pack:

```bash
brew install tesseract-lang    # macOS (requires Homebrew first)
```

After installing, **rebuild the index**.

### Problem 11: You want to wipe everything and start over

```bash
curl -X DELETE http://127.0.0.1:8000/api/index   # clear the index (understanding cache is kept)
rm -rf backend/data                               # full wipe (index + cache + thumbnails)
```

Afterwards, click 「构建索引」 ("Build Index") again.

### Problem 12: Still broken?

Copy the **complete red error text from the terminal** and include it when asking for help — the error message itself is the biggest clue.

---

## 8. How to Shut Down

| Situation | Action |
| --- | --- |
| Stop the frontend / backend | Go to the corresponding terminal window and press `Ctrl + C` (it's Ctrl on Mac too) |
| Kill all related processes | `pkill -f "uvicorn lumen.server:app"; pkill -f "next dev"` |
| Start it again later | Enter the project folder and repeat Section 4 (the second startup is fast — dependencies are already installed) |

After shutting down, the browser page will stop loading — that's normal. Your index and cache are saved under `backend/data/` and will still be there next time.

---

## 9. Mini Glossary

| Term | Plain-language explanation |
| --- | --- |
| **Index** | Writing a "content card" for every file, so searching flips through cards instead of re-reading files |
| **API Key** | A string of "pass" characters for using Google AI |
| **Gemini** | Google's AI model; it "understands" images and documents |
| **Embedding (vector)** | Turning a piece of text into a list of numbers; closer numbers = closer meaning — this powers semantic search |
| **Similarity score** | A value from 0 to 1 showing how well a result matches your search |
| **Cache** | The AI's answers are stored, so the same file isn't asked twice — saves time and quota |
| **429 / Quota** | The error code meaning "free quota used up" |
| **Offline mode** | A fallback mode that works without internet, understanding files via color, dimensions, and OCR |
| **Virtual environment (venv)** | A separate little "room" for Python; the packages this project installs don't affect anything else on your computer |
