// Thin fetch wrapper: cookies for auth, the CSRF header the server requires, typed errors.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fields?: { field: string; message: string }[]) {
    super(message);
  }
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Requested-With", "nyaya");
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers, body, credentials: "include" });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the server. Check that the backend is running and try again.");
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  const data = ct.includes("json") ? await res.json() : await res.blob();
  if (!res.ok) {
    const e = (data as { error?: { code: string; message: string; fields?: { field: string; message: string }[] } }).error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `Request failed (${res.status})`, e?.fields);
  }
  return data as T;
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- types mirroring the backend responses ----
export interface User { id: number; email: string; display_name: string; role: string }
export interface Citation {
  n: number; title: string; doc_type: string; identifier: string; authority: string; jurisdiction: string; ref: string;
  pages: [number | null, number | null]; url: string; publication_date: string | null; status: string; synthetic: boolean;
  version: string; ingested_at: string; excerpt: string; warnings: string[];
}
export interface AskResponse {
  conversation_id?: number; status: "ok" | "insufficient_evidence"; question: string; answer: string | null; answer_mode?: string; answer_note?: string;
  message?: string; citations: Citation[]; citation_report?: { total: number; valid: number; validity: number; issues: string[] };
  topic: { topic: string | null; confidence: string; model: string | null; model_error?: string; ranked: [string, number][] };
  retrieval: { components: string[]; corpus_chunks: number; skipped: Record<string, string> };
  sections: { uncertainties?: string[]; next_steps?: string[]; professional_advice?: string };
  clarifying_questions: string[]; urgent_contacts: { label: string; number: string }[]; disclaimer: string;
  models_used: { model: string; role: string }[]; timings: Record<string, number>;
  translation?: { translation: string; language: string; disclaimer: string; seconds: number }; translation_error?: string;
}
export interface Hit { chunk_id: number; score: number; text: string; ref_label: string; page_start: number | null; page_end: number | null; source: Source & { is_synthetic?: boolean }; warnings: string[]; ranks: Record<string, number> }
export interface Source { id: number; doc_type: string; title: string; identifier: string; authority: string; jurisdiction: string; source_url: string; publication_date: string | null; status: string; status_note?: string; version: string; synthetic?: boolean }
export interface DocSummary { id: number; name: string; size_bytes: number; sha256: string; status: "queued" | "processing" | "done" | "failed"; error: string; case_id: number | null; created_at: string; pages: number }
export interface Extracted { value: string | number; raw: string; page: number; context: string; label: string | null }
export interface DocDetail extends DocSummary {
  pages_text: { page: number; text: string; method: string }[];
  analysis: {
    extracted?: { dates: Extracted[]; amounts: Extracted[]; parties: { name: string | null; role?: string; page: number }[]; clauses: { number: string; heading: string; page: number }[]; obligations: { text: string; page: number }[] };
    unreadable_pages?: { page: number; reason: string }[]; notes?: string[];
    related_provisions?: { items: { title: string; ref: string; url: string; score: number; excerpt: string }[]; error: string | null; note: string };
  };
}
export interface TemplateField { key: string; label: string; help: string; required: boolean; type: string }
export interface Template { id: string; title: string; description: string; fields: TemplateField[]; authorities: string[] }
export interface Draft { id: number; template_id: string; title: string; facts: Record<string, string>; content: string; case_id: number | null; updated_at: string; revisions: number; missing: string[]; authorities?: { authority: string; verified_in_corpus: boolean; source_url: string | null; note: string }[] }
export interface CaseT { id: number; title: string; narrative: string; state: string; incident_date: string | null; facts: Record<string, unknown>; updated_at: string }
export interface AidEntry { id: string; name: string; type: string; stateOrUT: string; website: string; contactPhone?: string; helpline?: string; email?: string; address?: string; serviceDescription: string; eligibilityCriteria: string[]; sourceUrl: string; lastVerifiedDate: string }
export interface SystemStatus {
  models: { key: string; repo_id: string; revision: string; role: string; kind: string; downloaded: boolean; loaded: boolean; approx_disk_mb: number; approx_ram_mb: number }[];
  generator_backend: string; translation_languages: Record<string, string>; device: string;
  corpus: { sources: { doc_type: string; synthetic: boolean; count: number }[]; chunks: number }; limits: { max_upload_mb: number; max_pages: number };
}
