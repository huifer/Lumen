"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { BuildResponse, HealthResponse, SearchResponse } from "@/lib/types";
import ResultCard from "./ResultCard";

const EXAMPLES = ["红色背景的产品截图", "含有发票的文档", "海边日落照片", "合同金额"];

export default function Explorer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [root, setRoot] = useState("");
  const [backend, setBackend] = useState("offline");
  const [genModel, setGenModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [building, setBuilding] = useState(false);
  const [buildResult, setBuildResult] = useState<BuildResponse | null>(null);
  const [query, setQuery] = useState("");
  const [topk, setTopk] = useState(6);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((data) => {
        if (!alive) return;
        setHealth(data);
        setRoot(data.sample_root);
        setBackend(data.default_backend);
      })
      .catch((err: Error) => alive && setError(`连不上后端：${err.message}`));
    return () => {
      alive = false;
    };
  }, []);

  const handleBuild = useCallback(async () => {
    setBuilding(true);
    setError(null);
    try {
      const data = await api.build(root, backend, genModel || undefined, embedModel || undefined);
      setBuildResult(data);
      setHealth(await api.health());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBuilding(false);
    }
  }, [root, backend, genModel, embedModel]);

  const handleSearch = useCallback(
    async (q: string) => {
      const keyword = q.trim();
      if (!keyword) return;
      setSearching(true);
      setError(null);
      try {
        setResult(await api.search(keyword, topk));
        router.replace(`/?q=${encodeURIComponent(keyword)}`, { scroll: false });
      } catch (err) {
        setError((err as Error).message);
        setResult(null);
      } finally {
        setSearching(false);
      }
    },
    [topk, router],
  );

  // 支持用 ?q=xxx 直接分享/复现一次搜索
  const booted = useRef(false);
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const preset = searchParams.get("q");
    if (preset) {
      setQuery(preset);
      void handleSearch(preset);
    }
  }, [searchParams, handleSearch]);

  const hits = result?.hits ?? [];
  const maxScore = hits.length ? Math.max(...hits.map((h) => h.final_score)) : 1;

  return (
    <section className="panel">
      <div className="panel__row">
        <div className="field field--grow">
          <label htmlFor="root">索引目录</label>
          <input
            id="root"
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="要扫描的本地目录，例如 ~/Downloads"
            spellCheck={false}
          />
        </div>
        <div className="field">
          <label htmlFor="backend">理解后端</label>
          <select id="backend" value={backend} onChange={(e) => setBackend(e.target.value)}>
            <option value="offline">离线（无需 Key）</option>
            <option value="gemini" disabled={!health?.key_present}>
              Gemini（{health?.key_present ? "已检测到 Key" : "未配置 Key"}）
            </option>
          </select>
        </div>
        {health?.key_present ? (
          <>
            <div className="field">
              <label htmlFor="genModel">生成模型</label>
              <select id="genModel" value={genModel} onChange={(e) => setGenModel(e.target.value)}>
                <option value="">自动（{health.models.generation ?? "最新可用"}）</option>
                {health.models.generation_available.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="embedModel">向量模型</label>
              <select id="embedModel" value={embedModel} onChange={(e) => setEmbedModel(e.target.value)}>
                <option value="">自动（{health.models.embedding ?? "最新可用"}）</option>
                {health.models.embedding_available.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </>
        ) : null}
        <button className="btn btn--ghost" onClick={handleBuild} disabled={building}>
          {building ? "索引中…" : "构建索引"}
        </button>
      </div>

      <div className="panel__meta">
        <span className={`dot ${health?.key_present ? "dot--on" : "dot--off"}`} />
        <span>
          {health
            ? `后端 ${health.default_backend} · ${health.key_present ? "已配置 Gemini Key" : "无 Key（离线模式）"}`
            : "连接后端中…"}
        </span>
        <span className="panel__sep" />
        <span>已索引 {health?.indexed_files ?? 0} 个文件</span>
        {health?.models?.generation ? (
          <>
            <span className="panel__sep" />
            <span title={health.models.embedding ?? ""}>
              生成模型 {health.models.generation}
              {health.models.embedding ? ` · 向量模型 ${health.models.embedding}` : ""}
            </span>
          </>
        ) : null}
        {buildResult ? (
          <>
            <span className="panel__sep" />
            <span>
              本次索引 {buildResult.count} 个文件 · {buildResult.elapsed_ms}ms · 理解后端{" "}
              {buildResult.understander}
              {buildResult.understand_model ? `（${buildResult.understand_model}）` : ""}
            </span>
            {buildResult.models_used && Object.keys(buildResult.models_used).length > 0 ? (
              <>
                <span className="panel__sep" />
                <span>
                  本次调用{" "}
                  {Object.entries(buildResult.models_used)
                    .map(([m, n]) => `${m} ×${n}`)
                    .join("、")}
                </span>
              </>
            ) : (
              <>
                <span className="panel__sep" />
                <span>全部命中缓存，0 次模型调用</span>
              </>
            )}
            {buildResult.quota_exhausted && buildResult.quota_exhausted.length > 0 ? (
              <>
                <span className="panel__sep" />
                <span className="panel__warn">
                  配额已满：{buildResult.quota_exhausted.join("、")}
                </span>
              </>
            ) : null}
          </>
        ) : null}
      </div>

      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSearch(query);
        }}
      >
        <input
          className="search__input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="试试：红色背景的产品截图"
          aria-label="搜索查询"
        />
        <select
          className="search__topk"
          value={topk}
          onChange={(e) => setTopk(Number(e.target.value))}
          aria-label="返回条数"
        >
          {[4, 6, 8, 12].map((n) => (
            <option key={n} value={n}>
              Top {n}
            </option>
          ))}
        </select>
        <button className="btn btn--primary" type="submit" disabled={searching}>
          {searching ? "检索中…" : "搜索"}
        </button>
      </form>

      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            className="chip"
            onClick={() => {
              setQuery(ex);
              void handleSearch(ex);
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {error ? <p className="alert">{error}</p> : null}
      {buildResult?.warning ? <p className="alert alert--warn">{buildResult.warning}</p> : null}

      {result ? (
        <div className="results">
          <div className="results__head">
            <h2>
              {result.hits.length} 条结果
              {result.total ? <em> / 库中共 {result.total} 个文件</em> : null}
            </h2>
            <span className="results__timing">
              {result.took_ms && result.took_ms > 0 ? `${result.took_ms}ms` : "<1ms"} · {result.backend}
            </span>
          </div>

          {hits.length === 0 ? (
            <p className="empty">没有命中。换个说法，或先构建索引。</p>
          ) : (
            <div className="grid">
              {hits.map((hit) => (
                <ResultCard key={hit.path} hit={hit} maxScore={maxScore} />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
