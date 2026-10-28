import { Suspense } from "react";
import Explorer from "@/components/Explorer";

export default function Page() {
  return (
    <main className="shell">
      <header className="hero">
        <div className="hero__badge">NEXT.JS + FASTAPI · 本地运行</div>
        <h1 className="hero__title">
          Lumen <span>本地多模态文件检索</span>
        </h1>
        <p className="hero__sub">
          一句话，搜出散落在硬盘里的图片和文档。采集 → 理解 → 索引 → 检索 → 呈现，
          全流程在本地跑，不上传任何文件。
        </p>
      </header>
      <Suspense fallback={<p className="empty">加载中…</p>}>
        <Explorer />
      </Suspense>
    </main>
  );
}
