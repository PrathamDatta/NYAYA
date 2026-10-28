import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Download, FilePlus2, PenLine, RefreshCw, Save, Trash2, XCircle } from "lucide-react";
import { api, ApiError, download, type Draft, type Template } from "../lib/api";
import { Alert, Empty, ErrorBox, Field, PageHeader, Spinner, fmtDate } from "../components/ui";
import { useToast } from "../lib/toast";

export default function Drafts() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const caseId = sp.get("case") ? Number(sp.get("case")) : null;
  const [tpl, setTpl] = useState<Template[]>([]);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [pick, setPick] = useState<Template | null>(null);
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<Template[]>("/api/drafts/templates").then(setTpl).catch(setErr); api<Draft[]>("/api/drafts").then(setDrafts).catch(setErr); }, []);
  async function create() {
    if (!pick) return; setBusy(true); setErr(null);
    try { const d = await api<Draft>("/api/drafts", { method: "POST", json: { template_id: pick.id, facts, case_id: caseId } }); nav(`/app/drafts/${d.id}`); } catch (e) { setErr(e); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-8">
      <PageHeader title="Drafts">Build a document from structured facts, edit it, and export. Nothing is filed or sent for you.</PageHeader>
      {err ? <ErrorBox error={err} /> : null}
      {!pick ? (
        <section aria-labelledby="t"><h2 id="t" className="mb-3 text-xl font-semibold">Start a new draft</h2>
          <ul className="grid gap-3 sm:grid-cols-2">{tpl.map((t) => (<li key={t.id}><button onClick={() => setPick(t)} className="card h-full w-full p-4 text-left hover:border-brand"><span className="flex items-center gap-2 font-semibold"><FilePlus2 className="h-4 w-4 text-brass" aria-hidden />{t.title}</span><span className="mt-1 block text-sm text-muted">{t.description}</span></button></li>))}</ul></section>
      ) : (
        <section className="card space-y-4 p-5" aria-label={`New ${pick.title}`}>
          <div className="flex items-center justify-between"><h2 className="text-xl font-semibold">{pick.title}</h2><button className="btn-ghost" onClick={() => { setPick(null); setFacts({}); }}>Change template</button></div>
          <Alert>Leave a field blank if you don't know it yet — it will be clearly marked as missing in the draft.</Alert>
          {pick.fields.map((f) => (
            <Field key={f.key} label={`${f.label}${f.required ? "" : " (optional)"}`} help={f.help}>
              {f.type === "textarea" ? <textarea className="field min-h-[6rem]" value={facts[f.key] ?? ""} onChange={(e) => setFacts({ ...facts, [f.key]: e.target.value })} /> : <input className="field" value={facts[f.key] ?? ""} onChange={(e) => setFacts({ ...facts, [f.key]: e.target.value })} />}
            </Field>))}
          <p className="text-xs text-muted">Authorities this template relies on: {pick.authorities.join("; ")} — each is checked against the ingested corpus when the draft is created.</p>
          <button className="btn-primary" onClick={create} disabled={busy}>{busy ? <Spinner label="Creating…" /> : "Create draft"}</button>
        </section>
      )}
      <section aria-labelledby="mine"><h2 id="mine" className="mb-3 text-xl font-semibold">Your drafts</h2>
        {!drafts ? <Spinner label="Loading…" /> : drafts.length === 0 ? <Empty icon={<PenLine className="h-9 w-9" />} title="No drafts yet">Choose a template above to create your first draft.</Empty> : (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">{drafts.map((d) => (<li key={d.id}><Link to={`/app/drafts/${d.id}`} className="flex flex-wrap items-center justify-between gap-2 p-4 hover:bg-sunken"><span className="font-medium">{d.title}</span><span className="text-xs text-muted">{d.missing.length ? `${d.missing.length} fact${d.missing.length > 1 ? "s" : ""} missing · ` : ""}updated {fmtDate(d.updated_at)}</span></Link></li>))}</ul>)}
      </section>
    </div>
  );
}

export function DraftEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [d, setD] = useState<Draft | null>(null);
  const [tpl, setTpl] = useState<Template | null>(null);
  const [text, setText] = useState("");
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const load = useCallback(async () => {
    try { const x = await api<Draft>(`/api/drafts/${id}`); setD(x); setText(x.content); setFacts(x.facts); setDirty(false); setTpl((await api<Template[]>("/api/drafts/templates")).find((t) => t.id === x.template_id) ?? null); } catch (e) { setErr(e); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { const h = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); }; window.addEventListener("beforeunload", h); return () => window.removeEventListener("beforeunload", h); }, [dirty]);
  if (err) return <ErrorBox error={err} onRetry={() => void load()} />;
  if (!d || !tpl) return <Spinner label="Loading…" />;
  async function save(body: object, msg: string) { setBusy(true); try { const x = await api<Draft>(`/api/drafts/${id}`, { method: "PUT", json: body }); setD(x); setText(x.content); setFacts(x.facts); setDirty(false); toast("ok", msg); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Save failed"); } finally { setBusy(false); } }
  async function exp(format: "docx" | "txt") { try { const b = await api<Blob>(`/api/drafts/${id}/export?format=${format}`); download(b, `${d!.title.replace(/\W+/g, "_")}.${format}`); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Export failed"); } }
  return (
    <div className="space-y-5">
      <Link to="/app/drafts" className="inline-flex items-center gap-1 text-sm text-brand"><ArrowLeft className="h-4 w-4" aria-hidden />All drafts</Link>
      <PageHeader title={d.title} action={<div className="flex flex-wrap gap-2"><button className="btn-secondary" onClick={() => void exp("docx")}><Download className="h-4 w-4" aria-hidden />Word (.docx)</button><button className="btn-secondary" onClick={() => void exp("txt")}><Download className="h-4 w-4" aria-hidden />Text</button></div>}>{d.revisions} saved revision{d.revisions === 1 ? "" : "s"} · updated {fmtDate(d.updated_at)}</PageHeader>
      <Alert kind="warn" title="Draft for review — not filed, served or approved">Check every fact, date and authority, and have an advocate review before use. Exports are limited to Word and plain text.</Alert>
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-label="Draft text" className="space-y-3">
          <label htmlFor="draft" className="label">Edit the draft</label>
          <textarea id="draft" className="field min-h-[28rem] font-mono text-[13px] leading-relaxed" value={text} onChange={(e) => { setText(e.target.value); setDirty(true); }} />
          <div className="flex flex-wrap gap-2"><button className="btn-primary" disabled={busy || !dirty} onClick={() => void save({ content: text }, "Draft saved")}><Save className="h-4 w-4" aria-hidden />Save changes</button>
            <button className="btn-secondary !text-bad" onClick={async () => { await api(`/api/drafts/${id}`, { method: "DELETE" }); toast("ok", "Draft deleted"); nav("/app/drafts"); }}><Trash2 className="h-4 w-4" aria-hidden />Delete</button></div>
        </section>
        <aside className="space-y-5">
          {d.missing.length > 0 ? <Alert kind="warn" title={`${d.missing.length} fact${d.missing.length > 1 ? "s" : ""} still missing`}><ul className="list-disc pl-4">{d.missing.map((m) => <li key={m}>{m}</li>)}</ul></Alert> : <Alert kind="ok" title="All required facts supplied" >You can still add optional details.</Alert>}
          <section aria-label="Authorities" className="card p-4"><h2 className="mb-2 font-semibold">Authorities check</h2>
            <ul className="space-y-2 text-sm">{d.authorities?.map((a) => (<li key={a.authority} className="flex gap-2">{a.verified_in_corpus ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-label="found" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-label="not found" />}<span><b>{a.authority}</b><br /><span className="text-xs text-muted">{a.note}</span></span></li>))}</ul></section>
          <details className="card p-4"><summary className="cursor-pointer font-semibold">Edit facts and regenerate</summary>
            <div className="mt-3 space-y-3">{tpl.fields.map((f) => <Field key={f.key} label={f.label}>{f.type === "textarea" ? <textarea className="field min-h-[4rem]" value={facts[f.key] ?? ""} onChange={(e) => setFacts({ ...facts, [f.key]: e.target.value })} /> : <input className="field" value={facts[f.key] ?? ""} onChange={(e) => setFacts({ ...facts, [f.key]: e.target.value })} />}</Field>)}
              <p className="text-xs text-muted">Regenerating rebuilds the text from the facts. Your current text is kept as a revision.</p>
              <button className="btn-secondary" disabled={busy} onClick={() => void save({ facts }, "Draft regenerated")}><RefreshCw className="h-4 w-4" aria-hidden />Regenerate from facts</button></div></details>
        </aside>
      </div>
    </div>
  );
}
