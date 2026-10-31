"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { EXAMPLE_QUERIES, localizeBackendMessage, useI18n } from "@/lib/i18n";
import type { BuildResponse, HealthResponse, SearchResponse } from "@/lib/types";
import ResultCard from "./ResultCard";

export default function Explorer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale, t } = useI18n();
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
      .catch((err: Error) => alive && setError(t("errorBackend", { msg: err.message })));
    return () => {
      alive = false;
    };
  }, [t]);

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
        const data = await api.search(keyword, topk);
        if (!data.ok) {
          setError(localizeBackendMessage(data.error ?? "", locale, t));
          setResult(null);
        } else {
          setResult(data);
          router.replace(`/?q=${encodeURIComponent(keyword)}`, { scroll: false });
        }
      } catch (err) {
        setError(localizeBackendMessage((err as Error).message, locale, t));
        setResult(null);
      } finally {
        setSearching(false);
      }
    },
    [topk, router, locale, t],
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
  const examples = locale === "en" ? "en" : "zh";
  const joiner = locale === "en" ? ", " : "、";

  return (
    <section className="panel">
      <div className="panel__row">
        <div className="field field--grow">
          <label htmlFor="root">{t("indexDir")}</label>
          <input
            id="root"
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder={t("indexDirPlaceholder")}
            spellCheck={false}
          />
        </div>
        <div className="field">
          <label htmlFor="backend">{t("understandBackend")}</label>
          <select id="backend" value={backend} onChange={(e) => setBackend(e.target.value)}>
            <option value="offline">{t("offlineOption")}</option>
            <option value="gemini" disabled={!health?.key_present}>
              {health?.key_present ? t("geminiWithKey") : t("geminiNoKey")}
            </option>
          </select>
        </div>
        {health?.key_present ? (
          <>
            <div className="field">
              <label htmlFor="genModel">{t("genModel")}</label>
              <select id="genModel" value={genModel} onChange={(e) => setGenModel(e.target.value)}>
                <option value="">
                  {t("autoModel")}（{health.models.generation ?? t("autoModelFallback")}）
                </option>
                {health.models.generation_available.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="embedModel">{t("embedModel")}</label>
              <select id="embedModel" value={embedModel} onChange={(e) => setEmbedModel(e.target.value)}>
                <option value="">
                  {t("autoModel")}（{health.models.embedding ?? t("autoModelFallback")}）
                </option>
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
          {building ? t("building") : t("buildIndex")}
        </button>
      </div>

      <div className="panel__meta">
        <span className={`dot ${health?.key_present ? "dot--on" : "dot--off"}`} />
        <span>
          {health
            ? `${t("backendLabel")} ${health.default_backend} · ${health.key_present ? t("keyConfigured") : t("noKeyOffline")}`
            : t("connecting")}
        </span>
        <span className="panel__sep" />
        <span>{t("indexedCount", { n: health?.indexed_files ?? 0 })}</span>
        {health?.models?.generation ? (
          <>
            <span className="panel__sep" />
            <span title={health.models.embedding ?? ""}>
              {t("genModel")} {health.models.generation}
              {health.models.embedding ? ` · ${t("embedModel")} ${health.models.embedding}` : ""}
            </span>
          </>
        ) : null}
        {buildResult ? (
          <>
            <span className="panel__sep" />
            <span>
              {t("buildSummary", {
                n: buildResult.count,
                ms: buildResult.elapsed_ms,
                u: buildResult.understander,
              })}
              {buildResult.understand_model ? ` (${buildResult.understand_model})` : ""}
            </span>
            {buildResult.models_used && Object.keys(buildResult.models_used).length > 0 ? (
              <>
                <span className="panel__sep" />
                <span>
                  {t("apiCalls", {
                    calls: Object.entries(buildResult.models_used)
                      .map(([m, n]) => `${m} ×${n}`)
                      .join(joiner),
                  })}
                </span>
              </>
            ) : (
              <>
                <span className="panel__sep" />
                <span>{t("allCacheHits")}</span>
              </>
            )}
            {buildResult.quota_exhausted && buildResult.quota_exhausted.length > 0 ? (
              <>
                <span className="panel__sep" />
                <span className="panel__warn">
                  {t("quotaExhausted", { models: buildResult.quota_exhausted.join(joiner) })}
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
          placeholder={t("searchPlaceholder")}
          aria-label={t("ariaSearch")}
        />
        <select
          className="search__topk"
          value={topk}
          onChange={(e) => setTopk(Number(e.target.value))}
          aria-label={t("ariaTopk")}
        >
          {[4, 6, 8, 12].map((n) => (
            <option key={n} value={n}>
              Top {n}
            </option>
          ))}
        </select>
        <button className="btn btn--primary" type="submit" disabled={searching}>
          {searching ? t("searching") : t("searchButton")}
        </button>
      </form>

      <div className="examples">
        {EXAMPLE_QUERIES[examples].map((ex) => (
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
      {buildResult?.warning ? (
        <p className="alert alert--warn">{localizeBackendMessage(buildResult.warning, locale, t)}</p>
      ) : null}

      {result ? (
        <div className="results">
          <div className="results__head">
            <h2>
              {t("resultsCount", { n: result.hits.length })}
              {result.total ? <em> {t("ofTotal", { n: result.total })}</em> : null}
            </h2>
            <span className="results__timing">
              {result.took_ms && result.took_ms > 0 ? `${result.took_ms}ms` : "<1ms"} · {result.backend}
            </span>
          </div>

          {hits.length === 0 ? (
            <p className="empty">{t("noHits")}</p>
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
