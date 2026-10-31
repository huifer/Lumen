import { fileUrl, thumbUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Hit } from "@/lib/types";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ResultCard({ hit, maxScore }: { hit: Hit; maxScore: number }) {
  const { t } = useI18n();
  const ratio = maxScore > 0 ? Math.max(0.04, hit.final_score / maxScore) : 0;

  return (
    <article className="card">
      <div className="card__media">
        {hit.kind === "image" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbUrl(hit.path)} alt={hit.name} loading="lazy" />
        ) : (
          <div className={`card__file card__file--${hit.kind}`}>
            <span className="card__ext">{hit.ext.replace(".", "").toUpperCase() || "FILE"}</span>
            <span className="card__snippet">{hit.text_preview.slice(0, 120) || hit.title}</span>
          </div>
        )}
        <span className="card__score" title={`语义 ${hit.score} + 关键词 ${hit.keyword_bonus}`}>
          {hit.final_score.toFixed(3)}
        </span>
      </div>

      <div className="card__body">
        <h3 className="card__title" title={hit.name}>
          {hit.name}
        </h3>
        <p className="card__desc">{hit.description || hit.title}</p>

        {hit.tags.length > 0 && (
          <div className="card__tags">
            {hit.tags.slice(0, 5).map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        )}

        <div className="card__foot">
          <span className="card__path" title={hit.path}>
            {hit.rel_path}
          </span>
          <span className="card__size">{formatSize(hit.size)}</span>
        </div>

        <div className="card__bar" aria-hidden>
          <span style={{ width: `${ratio * 100}%` }} />
        </div>

        <a className="card__open" href={fileUrl(hit.path)} target="_blank" rel="noreferrer">
          {t("openOriginal")}
        </a>
      </div>
    </article>
  );
}
