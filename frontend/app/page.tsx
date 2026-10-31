import { Suspense } from "react";
import { LocaleProvider } from "@/lib/i18n";
import Hero from "@/components/Hero";
import Explorer from "@/components/Explorer";

export default function Page() {
  return (
    <main className="shell">
      <LocaleProvider>
        <Hero />
        <Suspense fallback={<p className="empty">…</p>}>
          <Explorer />
        </Suspense>
      </LocaleProvider>
    </main>
  );
}
