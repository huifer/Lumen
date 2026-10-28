export type FileKind = "image" | "pdf" | "doc" | "text" | "other";

export interface Hit {
  path: string;
  rel_path: string;
  name: string;
  ext: string;
  kind: FileKind;
  size: number;
  mtime: number;
  width: number | null;
  height: number | null;
  dominant: string | null;
  dominant_color_name: string | null;
  dominant_ratio: number | null;
  is_screenshot: boolean;
  title: string;
  description: string;
  tags: string[];
  ocr_text: string;
  text_preview: string;
  score: number;
  keyword_bonus: number;
  final_score: number;
}

export interface SearchResponse {
  ok: boolean;
  query?: string;
  backend?: string;
  took_ms?: number;
  total?: number;
  hits: Hit[];
  error?: string;
}

export interface BuildResponse {
  ok: boolean;
  backend: string;
  understander: string;
  count: number;
  root: string;
  elapsed_ms: number;
  model?: string | null;
  understand_model?: string | null;
  degraded?: boolean;
  warning?: string | null;
  models_used?: Record<string, number>;
  quota_exhausted?: string[];
  cache_entries?: number;
}

export interface HealthResponse {
  ok: boolean;
  default_backend: string;
  key_present: boolean;
  models: {
    generation: string | null;
    embedding: string | null;
    generation_available: string[];
    embedding_available: string[];
    available: string[];
    error: string | null;
  };
  indexed_files: number;
  sample_root: string;
  state: { status: string; message: string };
}
