import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Briefcase, Plus, Trash2 } from "lucide-react";
import { api, ApiError, type CaseT, type Draft, type DocSummary } from "../lib/api";
import { Dialog, Empty, ErrorBox, Field, PageHeader, Spinner, Alert, fmtDate } from "../components/ui";
import { useToast } from "../lib/toast";

export default function Cases() {
  const nav = useNavigate();
  const [cases, setCases] = useState<CaseT[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [form, setForm] = useState({ title: "", state: "", narrative: "" });
  const [open, setOpen] = useState(false);
  useEffect(() => { api<CaseT[]>("/api/cases").then(setCases).catch(setErr); }, []);
  async function create(e: FormEvent) { e.preventDefault(); try { const c = await api<CaseT>("/api/cases", { method: "POST", json: form }); nav(`/app/cases/${c.id}`); } catch (x) { setErr(x); } }
  return (
    <div>
      <PageHeader title="Cases" action={<button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" aria-hidden />New case</button>}>A private workspace that groups your questions, documents and drafts for one matter.</PageHeader>
      {err ? <ErrorBox error={err} /> : null}
      {!cases ? <Spinner label="Loading…" /> : cases.length === 0 ? <Empty icon={<Briefcase className="h-9 w-9" />} title="No cases yet" action={<button className="btn-primary" onClick={() => setOpen(true)}>Create your first case</button>}>Keep everything about one dispute together.</Empty> : (
        <ul className="divide-y divide-line rounded-xl border border-line bg-surface">{cases.map((c) => <li key={c.id}><Link to={`/app/cases/${c.id}`} className="flex flex-wrap items-center justify-between gap-2 p-4 hover:bg-sunken"><span className="font-medium">{c.title}</span><span className="text-xs text-muted">{c.state && `${c.state} · `}updated {fmtDate(c.updated_at)}</span></Link></li>)}</ul>)}
      <Dialog open={open} title="New case" onClose={() => setOpen(false)}>
        <form onSubmit={create} className="space-y-3">
          <Field label="Title"><input className="field" required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="State / UT (optional)"><input className="field" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} /></Field>
          <Field label="What happened (optional)"><textarea className="field min-h-[6rem]" value={form.narrative} onChange={(e) => setForm({ ...form, narrative: e.target.value })} /></Field>
          <div className="flex justify-end gap-2"><button type="button" className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary">Create</button></div>
        </form>
      </Dialog>
    </div>
  );
}

export function CaseDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [c, setC] = useState<CaseT | null>(null);
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [convs, setConvs] = useState<{ id: number; title: string; case_id: number | null }[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [confirm, setConfirm] = useState(false);
  const load = useCallback(async () => {
    try {
      const x = await api<CaseT>(`/api/cases/${id}`); setC(x);
      setDocs(await api<DocSummary[]>(`/api/documents?case_id=${id}`));
      setDrafts((await api<Draft[]>("/api/drafts")).filter((d) => d.case_id === x.id));
      setConvs((await api<typeof convs>("/api/conversations")).filter((v) => v.case_id === x.id));
    } catch (e) { setErr(e); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  if (err) return <ErrorBox error={err} onRetry={() => void load()} />;
  if (!c) return <Spinner label="Loading…" />;
  async function save() { try { await api(`/api/cases/${id}`, { method: "PUT", json: { title: c!.title, narrative: c!.narrative, state: c!.state, incident_date: c!.incident_date, facts: c!.facts } }); toast("ok", "Case saved"); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Save failed"); } }
  const List = ({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) => <section className="card p-4"><h2 className="mb-2 font-semibold">{title}</h2>{children.length ? <ul className="space-y-1 text-sm">{children}</ul> : <p className="text-sm text-muted">{empty}</p>}</section>;
  return (
    <div className="space-y-6">
      <Link to="/app/cases" className="inline-flex items-center gap-1 text-sm text-brand"><ArrowLeft className="h-4 w-4" aria-hidden />All cases</Link>
      <PageHeader title={c.title} action={<button className="btn-secondary !text-bad" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" aria-hidden />Delete case</button>} />
      <section className="card space-y-3 p-4">
        <Field label="Title"><input className="field" value={c.title} onChange={(e) => setC({ ...c, title: e.target.value })} /></Field>
        <div className="grid gap-3 sm:grid-cols-2"><Field label="State / UT"><input className="field" value={c.state} onChange={(e) => setC({ ...c, state: e.target.value })} /></Field><Field label="Date of incident"><input type="date" className="field" value={c.incident_date ?? ""} onChange={(e) => setC({ ...c, incident_date: e.target.value || null })} /></Field></div>
        <Field label="What happened"><textarea className="field min-h-[7rem]" value={c.narrative} onChange={(e) => setC({ ...c, narrative: e.target.value })} /></Field>
        <button className="btn-primary" onClick={() => void save()}>Save case</button>
      </section>
      <Alert>Documents, drafts and questions you create from the buttons below are attached to this case.</Alert>
      <div className="grid gap-4 md:grid-cols-3">
        <List title="Questions" empty="None yet.">{[...convs.map((v) => <li key={v.id}><Link className="text-brand hover:underline" to={`/app/ask/${v.id}?case=${c.id}`}>{v.title}</Link></li>), <li key="n"><Link className="btn-secondary mt-2" to={`/app/ask?case=${c.id}`}>Ask within this case</Link></li>]}</List>
        <List title="Documents" empty="None yet.">{[...docs.map((d) => <li key={d.id}><Link className="text-brand hover:underline" to={`/app/documents/${d.id}`}>{d.name}</Link></li>), <li key="n" className="pt-2"><CaseUpload caseId={c.id} onDone={load} /></li>]}</List>
        <List title="Drafts" empty="None yet.">{[...drafts.map((d) => <li key={d.id}><Link className="text-brand hover:underline" to={`/app/drafts/${d.id}`}>{d.title}</Link></li>), <li key="n"><Link className="btn-secondary mt-2" to={`/app/drafts?case=${c.id}`}>New draft for this case</Link></li>]}</List>
      </div>
      <Dialog open={confirm} title="Delete this case?" onClose={() => setConfirm(false)}>
        <p className="text-sm text-muted">The case record is deleted. Documents, drafts and conversations are kept but detached from it.</p>
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setConfirm(false)}>Cancel</button><button className="btn-danger" onClick={async () => { await api(`/api/cases/${id}`, { method: "DELETE" }); toast("ok", "Case deleted"); nav("/app/cases"); }}>Delete</button></div>
      </Dialog>
    </div>
  );
}

function CaseUpload({ caseId, onDone }: { caseId: number; onDone: () => void }) {
  const toast = useToast();
  return (
    <label className="btn-secondary cursor-pointer">Upload to this case
      <input type="file" hidden accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" onChange={async (e) => {
        const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); fd.append("case_id", String(caseId));
        try { await api("/api/documents", { method: "POST", body: fd }); toast("ok", "Uploaded — processing"); onDone(); } catch (x) { toast("error", x instanceof ApiError ? x.message : "Upload failed"); } e.target.value = "";
      }} />
    </label>
  );
}
