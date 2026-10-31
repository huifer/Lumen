"use client";

import { useI18n } from "@/lib/i18n";

export default function Hero() {
  const { locale, setLocale, t } = useI18n();

  return (
    <header className="hero">
      <div className="hero__top">
        <span className="hero__badge">{t("heroBadge")}</span>
        <button
          className="lang-toggle"
          onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
          aria-label={locale === "zh" ? "Switch to English" : "切换到中文"}
        >
          {locale === "zh" ? "EN" : "中文"}
        </button>
      </div>
      <h1 className="hero__title">
        Lumen <span>{t("appSubtitle")}</span>
      </h1>
      <p className="hero__sub">{t("heroSub")}</p>
    </header>
  );
}
