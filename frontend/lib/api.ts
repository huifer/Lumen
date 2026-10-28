import type { BuildResponse, HealthResponse, SearchResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `请求失败: ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  build: (root: string, backend: string, model?: string, embedModel?: string) =>
    request<BuildResponse>("/api/build", {
      method: "POST",
      body: JSON.stringify({ root, backend, model, embed_model: embedModel }),
    }),
  search: (query: string, topk: number) =>
    request<SearchResponse>("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, topk }),
    }),
};

export function thumbUrl(path: string) {
  return `${BASE}/api/thumb?path=${encodeURIComponent(path)}`;
}

export function fileUrl(path: string) {
  return `${BASE}/api/file?path=${encodeURIComponent(path)}`;
}
