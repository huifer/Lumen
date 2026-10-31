import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lumen · 本地多模态文件检索 | Local Multimodal File Search",
  description:
    "用自然语言搜出你本地的图片与文档 · Next.js + FastAPI demo — Search your local images and documents in natural language.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
