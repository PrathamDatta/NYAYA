import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, FileText, RotateCw, Trash2, Upload } from "lucide-react";
import { api, ApiError, type DocDetail, type DocSummary, type SystemStatus } from "../lib/api";
import { Alert, Badge, Dialog, Empty, ErrorBox, PageHeader, Spinner, fmtBytes, fmtDate } from "../components/ui";
import { useToast } from "../lib/toast";

const tone = { queued: "neutral", processing: "brand", done: "ok", failed: "bad" } as const;

export default function Documents() {
  const toast = useToast();
  const [docs, setDocs] = useState<DocSummary[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [limit, setLimit] = useState(15);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<DocSummary[]>("/api/documents").then(setDocs).catch(setErr), []);
  useEffect(() => { void load(); api<SystemStatus>("/api/system/status").then((s) => setLimit(s.limits.max_upload_mb)).catch(() => {}); }, [load]);
  useEffect(() => { // poll only while something is actually in progress
    if (!docs?.some((d) => d.status === "queued" || d.status === "processing")) return;
    const t = setInterval(() => void load(), 1500); return () => clearInterval(t);
  }, [docs, load]);

  async function upload(files: FileList | File[]) {
    setUploading(true);
    for (const f of Array.from(files)) {
      if (f.size > limit * 1048576) { toast("error", `${f.name} is larger than ${limit} MB`); continue; }
      const fd = new FormData(); fd.append("file", f);
      try { await api("/api/documents", { method: "POST", body: fd }); toast("ok", `${f.name} uploaded — processing`); } catch (e) { toast("error", `${f.name}: ${e instanceof ApiError ? e.message : "upload failed"}`); }
    }
    setUploading(false); void load();
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) void upload(e.dataTransfer.files); };

  return (
    <div>
      <PageHeader title="Documents">Upload agreements, notices, invoices or correspondence. Text and key facts are extracted with page references.</PageHeader>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
        className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${drag ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
        <Upload className="mx-auto h-8 w-8 text-brass" aria-hidden />
        <p className="mt-2 font-semibold">Drop files here or</p>
        <button className="btn-primary mt-2" onClick={() => input.current?.click()} disabled={uploading}>{uploading ? <Spinner label="Uploading…" /> : "Choose files"}</button>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" aria-label="Upload documents" onChange={(e) => e.target.files && void upload(e.target.files)} />
        <p className="mt-3 text-xs text-muted">PDF, Word (.docx), text, and PNG/JPEG images (needs the optional OCR package). Up to {limit} MB each. Stored privately; delete any time.</p>
      </div>
      <div className="mt-6 space-y-3">
        {err ? <ErrorBox error={err} onRetry={() => void load()} /> : null}
        {!docs && !err && <Spinner label="Loading…" />}
        {docs && docs.length === 0 && <Empty icon={<FileText className="h-9 w-9" />} title="No documents yet">Upload a document to extract its dates, amounts, parties and clauses.</Empty>}
        {docs && docs.length > 0 && (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">{docs.map((d) => (
              <li key={d.id}><Link to={`/app/documents/${d.id}`} className="flex flex-wrap items-center justify-between gap-2 p-4 hover:bg-sunken">
                <span className="min-w-0"><span className="block truncate font-medium">{d.name}</span><span className="text-xs text-muted">{fmtBytes(d.size_bytes)} · {d.pages} page{d.pages === 1 ? "" : "s"} · {fmtDate(d.created_at)}</span></span>
                <span className="flex items-center gap-2">{(d.status === "processing" || d.status === "queued") && <Spinner />}<Badge tone={tone[d.status]}>{d.status}</Badge></span></Link></li>))}</ul>
        )}
        <Inconsistencies enabled={!!docs && docs.filter((d) => d.status === "done").length > 1} />
      </div>
    </div>
  );
}

function Inconsistencies({ enabled }: { enabled: boolean }) {
  const [items, setItems] = useState<{ kind: string; label: string; values: (string | number)[]; occurrences: { document: string; page: number; raw: string; context: string }[]; note: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  if (!enabled) return null;
  async function run() { setBusy(true); try { setItems((await api<{ items: NonNullable<typeof items> }>("/api/documents/inconsistencies")).items); } finally { setBusy(false); } }
  return (
    <section className="card p-4" aria-label="Cross-document check">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-semibold">Cross-document check</h2><p className="text-sm text-muted">Looks for the same term (e.g. “deposit”) with different amounts or dates in different documents.</p></div><button className="btn-secondary" onClick={run} disabled={busy}>{busy ? <Spinner label="Checking…" /> : "Check my documents"}</button></div>
      {items && (items.length === 0 ? <p className="mt-3 text-sm text-ok">No differing values found near the same terms. This does not prove the documents agree.</p> :
        <ul className="mt-3 space-y-3">{items.map((i, k) => (
          <li key={k} className="rounded-lg bg-warn-soft p-3 text-sm text-ink"><p className="flex items-center gap-2 font-semibold text-warn"><AlertTriangle className="h-4 w-4" aria-hidden />Possible inconsistency in “{i.label}” ({i.kind}): {i.values.join(" vs ")}</p>
            <ul className="mt-1 list-disc pl-5 text-xs text-muted">{i.occurrences.map((o, j) => <li key={j}>{o.document}, p.{o.page}: “…{o.context}…”</li>)}</ul><p className="mt-1 text-xs text-muted">{i.note}</p></li>))}</ul>)}
    </section>
  );
}

export function DocumentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [d, setD] = useState<DocDetail | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [tab, setTab] = useState<"facts" | "text" | "related">("facts");
  const [confirm, setConfirm] = useState(false);
  const load = useCallback(() => api<DocDetail>(`/api/documents/${id}`).then(setD).catch(setErr), [id]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (d && (d.status === "queued" || d.status === "processing")) { const t = setTimeout(() => void load(), 1200); return () => clearTimeout(t); } }, [d, load]);
  if (err) return <ErrorBox error={err} onRetry={() => void load()} />;
  if (!d) return <Spinner label="Loading…" />;
  const ex = d.analysis.extracted;
  const Table = ({ rows, cols }: { rows: (string | number)[][]; cols: string[] }) => (
    <div className="overflow-x-auto rounded-lg border border-line"><table className="w-full min-w-[32rem] text-left text-sm"><thead className="bg-sunken text-muted"><tr>{cols.map((c) => <th key={c} scope="col" className="px-3 py-2 font-medium">{c}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line align-top">{r.map((c, j) => <td key={j} className="px-3 py-2">{c}</td>)}</tr>)}</tbody></table></div>);
  return (
    <div className="space-y-5">
      <Link to="/app/documents" className="inline-flex items-center gap-1 text-sm text-brand"><ArrowLeft className="h-4 w-4" aria-hidden />All documents</Link>
      <PageHeader title={d.name} action={<div className="flex gap-2"><button className="btn-secondary" onClick={async () => { await api(`/api/documents/${d.id}/retry`, { method: "POST" }); void load(); }}><RotateCw className="h-4 w-4" aria-hidden />Re-process</button><button className="btn-secondary !text-bad" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" aria-hidden />Delete</button></div>}>
        {fmtBytes(d.size_bytes)} · uploaded {fmtDate(d.created_at)} · <Badge tone={tone[d.status]}>{d.status}</Badge> · SHA-256 <span className="font-mono text-xs">{d.sha256.slice(0, 12)}…</span></PageHeader>
      {(d.status === "queued" || d.status === "processing") && <Spinner label="Extracting text and facts…" />}
      {d.status === "failed" && <Alert kind="error" title="This document could not be processed">{d.error}</Alert>}
      {d.status === "done" && (
        <>
          {d.analysis.unreadable_pages && d.analysis.unreadable_pages.length > 0 && <Alert kind="warn" title="Some pages had no readable text">Pages {d.analysis.unreadable_pages.map((p) => p.page).join(", ")}: {d.analysis.unreadable_pages[0].reason}.</Alert>}
          <div role="tablist" className="inline-flex rounded-lg border border-line bg-surface p-1">{([["facts", "Extracted facts"], ["related", "Related provisions"], ["text", "Full text"]] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`rounded-md px-4 py-2 text-sm font-semibold ${tab === k ? "bg-brand-soft text-brand-strong" : "text-muted"}`}>{l}</button>)}</div>
          {tab === "facts" && ex && (
            <div className="space-y-6">
              <Alert>These values are pattern-matched from the text and shown with page numbers. They are facts as written in your document, not legal conclusions — check them against the original.</Alert>
              <section><h2 className="mb-2 text-lg font-semibold">Dates</h2>{ex.dates.length ? <Table cols={["Date", "As written", "Near", "Page"]} rows={ex.dates.map((x) => [fmtDate(String(x.value)), x.raw, x.label ?? "—", x.page])} /> : <p className="text-sm text-muted">None found.</p>}</section>
              <section><h2 className="mb-2 text-lg font-semibold">Amounts</h2>{ex.amounts.length ? <Table cols={["Amount (₹)", "As written", "Near", "Page"]} rows={ex.amounts.map((x) => [Number(x.value).toLocaleString("en-IN"), x.raw, x.label ?? "—", x.page])} /> : <p className="text-sm text-muted">None found.</p>}</section>
              <section><h2 className="mb-2 text-lg font-semibold">Parties & roles</h2>{ex.parties.length ? <Table cols={["Name / role", "Page"]} rows={ex.parties.map((p) => [p.name ?? `defined as “${p.role}”`, p.page])} /> : <p className="text-sm text-muted">None found.</p>}</section>
              <section><h2 className="mb-2 text-lg font-semibold">Clauses</h2>{ex.clauses.length ? <Table cols={["No.", "Heading", "Page"]} rows={ex.clauses.map((c) => [c.number, c.heading, c.page])} /> : <p className="text-sm text-muted">No numbered clauses detected.</p>}</section>
              <section><h2 className="mb-2 text-lg font-semibold">Candidate obligations</h2>{ex.obligations.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{ex.obligations.map((o, i) => <li key={i}>{o.text} <span className="text-muted">(p.{o.page})</span></li>)}</ul> : <p className="text-sm text-muted">None detected.</p>}</section>
            </div>
          )}
          {tab === "related" && (
            <div className="space-y-3"><Alert kind="warn" title="Model-suggested, not a conclusion">{d.analysis.related_provisions?.note}</Alert>
              {d.analysis.related_provisions?.error && <Alert kind="error">Retrieval models unavailable: {d.analysis.related_provisions.error}</Alert>}
              {d.analysis.related_provisions?.items.length === 0 && !d.analysis.related_provisions.error && <Empty icon={<FileText className="h-8 w-8" />} title="No related provisions found">The indexed corpus has nothing close to this document's opening text.</Empty>}
              {d.analysis.related_provisions?.items.map((r, i) => <article key={i} className="card p-4"><h3 className="font-semibold">{r.title}</h3><p className="text-xs text-muted">{r.ref}</p><p className="mt-1 text-sm">{r.excerpt}…</p></article>)}</div>
          )}
          {tab === "text" && <div className="space-y-4">{d.pages_text.map((p) => <section key={p.page} className="card p-4"><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Page {p.page} · {p.method === "ocr" ? "OCR" : "text layer"}</h3><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">{p.text || "(no text)"}</pre></section>)}</div>}
        </>
      )}
      <Dialog open={confirm} title="Delete this document?" onClose={() => setConfirm(false)}>
        <p className="text-sm text-muted">The file and everything extracted from it will be permanently removed.</p>
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setConfirm(false)}>Cancel</button><button className="btn-danger" onClick={async () => { await api(`/api/documents/${d.id}`, { method: "DELETE" }); toast("ok", "Document deleted"); nav("/app/documents"); }}>Delete</button></div>
      </Dialog>
    </div>
  );
}
