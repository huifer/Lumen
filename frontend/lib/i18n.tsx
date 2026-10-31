"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type Locale = "zh" | "en";

const zh = {
  appSubtitle: "本地多模态文件检索",
  heroBadge: "NEXT.JS + FASTAPI · 本地运行",
  heroSub:
    "一句话，搜出散落在硬盘里的图片和文档。采集 → 理解 → 索引 → 检索 → 呈现，全流程在本地跑，不上传任何文件。",
  indexDir: "索引目录",
  indexDirPlaceholder: "要扫描的本地目录，例如 ~/Downloads",
  understandBackend: "理解后端",
  offlineOption: "离线（无需 Key）",
  geminiWithKey: "Gemini（已检测到 Key）",
  geminiNoKey: "Gemini（未配置 Key）",
  genModel: "生成模型",
  embedModel: "向量模型",
  autoModel: "自动",
  autoModelFallback: "最新可用",
  buildIndex: "构建索引",
  building: "索引中…",
  backendLabel: "后端",
  keyConfigured: "已配置 Gemini Key",
  noKeyOffline: "无 Key（离线模式）",
  connecting: "连接后端中…",
  indexedCount: "已索引 {n} 个文件",
  buildSummary: "本次索引 {n} 个文件 · {ms}ms · 理解后端 {u}",
  apiCalls: "本次调用 {calls}",
  allCacheHits: "全部命中缓存，0 次模型调用",
  quotaExhausted: "配额已满：{models}",
  searchButton: "搜索",
  searching: "检索中…",
  searchPlaceholder: "试试：红色背景的产品截图",
  ariaSearch: "搜索查询",
  ariaTopk: "返回条数",
  resultsCount: "{n} 条结果",
  ofTotal: "/ 库中共 {n} 个文件",
  noHits: "没有命中。换个说法，或先构建索引。",
  openOriginal: "打开原文件 ↗",
  errorBackend: "连不上后端：{msg}",
  errorIndexEmpty: "索引为空，请先构建索引",
  errorEmptyQuery: "查询不能为空",
  errorDimMismatch: "索引向量维度与当前模型不一致，请重新构建索引",
  geminiFallbackWarnPrefix: "Gemini 后端不可用，已自动降级为离线模式：",
};

const en: typeof zh = {
  appSubtitle: "Local Multimodal File Search",
  heroBadge: "NEXT.JS + FASTAPI · RUNS LOCALLY",
  heroSub:
    "Find the images and documents scattered across your disk with a single sentence. Ingest → Understand → Index → Retrieve → Present — everything runs locally, and no file ever leaves your machine.",
  indexDir: "Index directory",
  indexDirPlaceholder: "Local directory to scan, e.g. ~/Downloads",
  understandBackend: "Understanding backend",
  offlineOption: "Offline (no key needed)",
  geminiWithKey: "Gemini (key detected)",
  geminiNoKey: "Gemini (key not configured)",
  genModel: "Generation model",
  embedModel: "Embedding model",
  autoModel: "Auto",
  autoModelFallback: "latest available",
  buildIndex: "Build index",
  building: "Indexing…",
  backendLabel: "Backend",
  keyConfigured: "Gemini key configured",
  noKeyOffline: "no key (offline mode)",
  connecting: "Connecting to backend…",
  indexedCount: "{n} files indexed",
  buildSummary: "Indexed {n} files · {ms}ms · understander {u}",
  apiCalls: "Model calls: {calls}",
  allCacheHits: "All cache hits, 0 model calls",
  quotaExhausted: "Quota exhausted: {models}",
  searchButton: "Search",
  searching: "Searching…",
  searchPlaceholder: "Try: product screenshot with a red background",
  ariaSearch: "Search query",
  ariaTopk: "Number of results",
  resultsCount: "{n} results",
  ofTotal: "of {n} files in the index",
  noHits: "No hits. Try rephrasing, or build the index first.",
  openOriginal: "Open original ↗",
  errorBackend: "Cannot reach the backend: {msg}",
  errorIndexEmpty: "The index is empty. Build it first.",
  errorEmptyQuery: "Query cannot be empty",
  errorDimMismatch: "Index vector dimensions do not match the current model. Please rebuild the index.",
  geminiFallbackWarnPrefix: "Gemini backend unavailable, fell back to offline mode: ",
};

const messages: Record<Locale, typeof zh> = { zh, en };

export const EXAMPLE_QUERIES: Record<Locale, string[]> = {
  zh: ["红色背景的产品截图", "含有发票的文档", "海边日落照片", "合同金额"],
  en: [
    "Product screenshot with a red background",
    "Documents containing invoices",
    "Sunset over the sea photo",
    "Contract amount",
  ],
};

export type MessageKey = keyof typeof zh;
export type TranslateValues = Record<string, string | number>;

/** 把后端返回的中文提示映射成当前语言（未命中时原样返回）。 */
export function localizeBackendMessage(
  raw: string,
  locale: Locale,
  t: (key: MessageKey, values?: TranslateValues) => string,
): string {
  if (!raw) return raw;
  if (locale !== "en") return raw;
  if (raw.includes("索引为空")) return t("errorIndexEmpty");
  if (raw.includes("查询不能为空")) return t("errorEmptyQuery");
  if (raw.includes("维度不一致")) return t("errorDimMismatch");
  if (raw.startsWith("Gemini 后端不可用")) {
    return t("geminiFallbackWarnPrefix") + raw.slice("Gemini 后端不可用，已自动降级为离线模式：".length);
  }
  return raw;
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, values?: TranslateValues) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "lumen_locale";

export function LocaleProvider({ children }: { children: ReactNode }) {
  // SSR 首帧渲染中文；挂载后按 ?lang= > localStorage > 浏览器语言 决定最终语言
  const [locale, setLocaleState] = useState<Locale>("zh");

  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("lang");
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const browser: Locale = navigator.language.toLowerCase().startsWith("en") ? "en" : "zh";
    const next: Locale =
      param === "en" || param === "zh"
        ? param
        : stored === "en" || stored === "zh"
          ? stored
          : browser;
    setLocaleState(next);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* localStorage 不可用时忽略 */
    }
  }, []);

  const t = useCallback(
    (key: MessageKey, values?: TranslateValues) => {
      let text: string = messages[locale][key] ?? key;
      if (values) {
        for (const [name, value] of Object.entries(values)) {
          text = text.replaceAll(`{${name}}`, String(value));
        }
      }
      return text;
    },
    [locale],
  );

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within LocaleProvider");
  return ctx;
}
