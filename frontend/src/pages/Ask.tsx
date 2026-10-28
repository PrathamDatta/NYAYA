import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AlertTriangle, BookOpen, ChevronDown, ExternalLink, History, MessageSquarePlus, Phone, SearchX, SendHorizonal, Trash2, Languages, ShieldCheck } from "lucide-react";
import { api, ApiError, type AskResponse, type Citation } from "../lib/api";
import { Alert, Badge, Empty, ErrorBox, PageHeader, Spinner, docTypeLabel, fmtDate } from "../components/ui";
import { useToast } from "../lib/toast";

interface Msg { id?: number; role: "user" | "assistant"; content: string; payload?: AskResponse }
interface Conv { id: number; title: string; created_at: string }

function CitationCard({ c }: { c: Citation }) {
  const [open, setOpen] = useState(false);
  const pages = c.pages[0] ? (c.pages[1] && c.pages[1] !== c.pages[0] ? `pp. ${c.pages[0]}–${c.pages[1]}` : `p. ${c.pages[0]}`) : null;
  return (
    <li id={`s${c.n}`} className="rounded-lg border border-line bg-surface">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-start gap-3 p-3 text-left">
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded bg-brand-soft text-xs font-bold text-brand-strong">S{c.n}</span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium leading-snug">{c.title}</span>
          <span className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <Badge tone="brand">{docTypeLabel(c.doc_type)}</Badge>
            <span>{c.ref}{pages ? ` · ${pages}` : ""}</span>{c.identifier && <span>· {c.identifier}</span>}{c.publication_date && <span>· {fmtDate(c.publication_date)}</span>}
            {c.synthetic && <Badge tone="bad">synthetic test data — not real law</Badge>}
            {c.status === "unknown" && !c.synthetic && c.doc_type !== "judgment" && <Badge tone="warn">in-force status unverified</Badge>}
          </span>
        </span>
        <ChevronDown className={`mt-1 h-4 w-4 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <div className="space-y-2 border-t border-line p-3 text-sm">
          <blockquote className="border-l-2 border-brass pl-3 leading-relaxed text-ink/90">{c.excerpt}{c.excerpt.length >= 700 ? "…" : ""}</blockquote>
          {c.warnings.map((w) => <p key={w} className="flex items-center gap-1.5 text-warn"><AlertTriangle className="h-3.5 w-3.5" aria-hidden />{w}</p>)}
          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span>{c.authority} · {c.jurisdiction}</span><span>Ingested {fmtDate(c.ingested_at)} · v{c.version}</span>
            {c.url && !c.synthetic && <a className="inline-flex items-center gap-1 font-semibold text-brand hover:underline" href={c.url} target="_blank" rel="noreferrer">Open original source<ExternalLink className="h-3 w-3" aria-hidden /></a>}
          </p>
        </div>
      )}
    </li>
  );
}

function TranslatePanel({ r }: { r: AskResponse }) {
  const [langs, setLangs] = useState<Record<string, string>>({});
  const [lang, setLang] = useState("hi");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<{ translation: string; language: string; disclaimer: string } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api<{ translation_languages: Record<string, string> }>("/api/system/status").then((s) => setLangs(s.translation_languages)).catch(() => {}); }, []);
  const text = [...(r.sections.next_steps ?? []), r.sections.professional_advice ?? ""].filter(Boolean).join("\n");
  async function go() {
    setBusy(true); setErr(null);
    try { setOut(await api("/api/translate", { method: "POST", json: { text, target: lang } })); } catch (e) { setErr(e); } finally { setBusy(false); }
  }
  return (
    <details className="rounded-lg border border-line p-3 text-sm">
      <summary className="flex cursor-pointer items-center gap-2 font-medium"><Languages className="h-4 w-4 text-brass" aria-hidden />Read the next steps in another language</summary>
      <div className="mt-3 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor={`lang-${r.conversation_id}`}>Language</label>
          <select id={`lang-${r.conversation_id}`} className="field !w-auto" value={lang} onChange={(e) => setLang(e.target.value)}>{Object.entries(langs).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select>
          <button className="btn-secondary" onClick={go} disabled={busy}>{busy ? <Spinner label="Translating (the first run loads a ~4 GB model)…" /> : "Translate"}</button>
        </div>
        {err ? <ErrorBox error={err} onRetry={go} /> : null}
        {out && <div className="space-y-2"><p className="indic whitespace-pre-line rounded-lg bg-sunken p-3 text-base">{out.translation}</p><p className="text-xs text-muted">{out.disclaimer}</p></div>}
      </div>
    </details>
  );
}

export function AnswerCard({ r, onAsk }: { r: AskResponse; onAsk: (q: string) => void }) {
  const [how, setHow] = useState(false);
  return (
    <div className="space-y-4">
      {r.urgent_contacts.length > 0 && (
        <Alert kind="error" title="If this is urgent, call now">
          <ul className="mt-1 flex flex-wrap gap-2">{r.urgent_contacts.map((c) => <li key={c.number}><a className="inline-flex items-center gap-1.5 rounded-lg bg-surface px-3 py-2 font-semibold text-ink" href={`tel:${c.number}`}><Phone className="h-4 w-4" aria-hidden />{c.label}: {c.number}</a></li>)}</ul>
        </Alert>
      )}
      {r.status === "insufficient_evidence" ? (
        <Alert kind="warn" title="The indexed sources don't support an answer"><p>{r.message}</p></Alert>
      ) : (
        <>
          <section aria-label="What the sources say" className="space-y-2">
            <div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-semibold">What the sources say</h3>
              <Badge tone={r.answer_mode === "extractive" ? "neutral" : "brand"}>{r.answer_mode === "extractive" ? "verbatim excerpts" : "generated from sources"}</Badge>
              {r.citation_report && <Badge tone={r.citation_report.validity === 1 ? "ok" : "warn"}>{r.citation_report.valid}/{r.citation_report.total} citations verified</Badge>}</div>
            <div className="prose-legal whitespace-pre-line rounded-lg bg-sunken p-4 leading-relaxed">{r.answer}</div>
            {r.answer_note && <p className="text-xs text-muted">{r.answer_note}</p>}
          </section>
          <section aria-label="Sources"><h3 className="mb-2 flex items-center gap-2 text-lg font-semibold"><BookOpen className="h-4 w-4 text-brass" aria-hidden />Sources</h3><ul className="space-y-2">{r.citations.map((c) => <CitationCard key={c.n} c={c} />)}</ul></section>
          {r.sections.uncertainties && r.sections.uncertainties.length > 0 && <section aria-label="Uncertainties"><h3 className="mb-1 text-lg font-semibold">What we're unsure about</h3><ul className="list-disc space-y-1 pl-5 text-sm text-muted">{r.sections.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul></section>}
        </>
      )}
      {r.clarifying_questions.length > 0 && (
        <section aria-label="Questions that would sharpen this"><h3 className="mb-1 text-lg font-semibold">Details that would change the answer</h3>
          <ul className="space-y-1.5">{r.clarifying_questions.map((q) => <li key={q}><button className="text-left text-sm text-brand hover:underline" onClick={() => onAsk(q)}>{q}</button></li>)}</ul></section>
      )}
      {r.status === "ok" && r.sections.next_steps && (
        <section aria-label="Next steps"><h3 className="mb-1 text-lg font-semibold">Practical next steps</h3><ol className="list-decimal space-y-1 pl-5 text-sm">{r.sections.next_steps.map((s) => <li key={s}>{s}</li>)}</ol>
          {r.sections.professional_advice && <p className="mt-3 flex items-start gap-2 text-sm text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{r.sections.professional_advice}</p>}</section>
      )}
      {r.status === "ok" && <TranslatePanel r={r} />}
      <p className="text-xs leading-relaxed text-muted">{r.disclaimer}</p>
      <button onClick={() => setHow(!how)} className="text-xs font-medium text-muted underline" aria-expanded={how}>How was this produced?</button>
      {how && (
        <dl className="grid gap-x-6 gap-y-1 rounded-lg border border-line p-3 text-xs text-muted sm:grid-cols-2">
          <dt>Retrieval components</dt><dd>{r.retrieval.components.join(", ")}{Object.keys(r.retrieval.skipped).length > 0 && <span className="text-warn"> · skipped: {Object.entries(r.retrieval.skipped).map(([k, v]) => `${k} (${v})`).join("; ")}</span>}</dd>
          <dt>Passages indexed</dt><dd>{r.retrieval.corpus_chunks}</dd>
          <dt>Topic</dt><dd>{r.topic.topic ?? "unknown"} ({r.topic.confidence}){r.topic.model ? ` · ${r.topic.model}` : r.topic.model_error ? ` · model unavailable: ${r.topic.model_error}` : ""}</dd>
          <dt>Models used</dt><dd>{r.models_used.map((m) => `${m.model} (${m.role})`).join("; ") || "none (lexical only)"}</dd>
          <dt>Answer mode</dt><dd>{r.answer_mode ?? "n/a"}</dd>
          <dt>Time</dt><dd>{Object.entries(r.timings).map(([k, v]) => `${k.replace("_s", "")} ${v}s`).join(" · ")}</dd>
        </dl>
      )}
    </div>
  );
}

export default function Ask() {
  const { id } = useParams();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const caseId = sp.get("case") ? Number(sp.get("case")) : undefined;
  const toast = useToast();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [err, setErr] = useState<unknown>(null);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [showList, setShowList] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  const loadList = useCallback(() => api<Conv[]>("/api/conversations").then(setConvs).catch(setLoadErr), []);
  useEffect(() => { void loadList(); }, [loadList]);
  useEffect(() => {
    if (!id) { setMsgs([]); return; }
    setLoadErr(null);
    api<{ messages: { id: number; role: "user" | "assistant"; content: string; payload: AskResponse }[] }>(`/api/conversations/${id}`)
      .then((c) => setMsgs(c.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, payload: m.role === "assistant" ? m.payload : undefined }))))
      .catch(setLoadErr);
  }, [id]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);
  useEffect(() => {
    if (!busy) return; const t0 = Date.now(); const i = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 500); return () => { clearInterval(i); setElapsed(0); };
  }, [busy]);

  async function send(text: string) {
    if (text.trim().length < 5 || busy) return;
    setErr(null); setBusy(true); setQ("");
    setMsgs((m) => [...m, { role: "user", content: text }]);
    try {
      const r = await api<AskResponse>("/api/ask", { method: "POST", json: { question: text, conversation_id: id ? Number(id) : undefined, case_id: caseId } });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer ?? r.message ?? "", payload: r }]);
      void loadList();
      if (!id && r.conversation_id) nav(`/app/ask/${r.conversation_id}${caseId ? `?case=${caseId}` : ""}`, { replace: true });
    } catch (e) { setErr(e); setQ(text); setMsgs((m) => m.slice(0, -1)); } finally { setBusy(false); }
  }
  async function del(cid: number) {
    try { await api(`/api/conversations/${cid}`, { method: "DELETE" }); toast("ok", "Conversation deleted"); if (String(cid) === id) nav("/app/ask"); void loadList(); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Could not delete"); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void send(q); };

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
      <aside className={`${showList ? "block" : "hidden"} lg:block`} aria-label="Conversation history">
        <Link to="/app/ask" className="btn-secondary mb-3 w-full" onClick={() => setShowList(false)}><MessageSquarePlus className="h-4 w-4" aria-hidden />New question</Link>
        {convs.length === 0 ? <p className="text-sm text-muted">Your past questions will appear here.</p> : (
          <ul className="space-y-1">{convs.map((c) => (
            <li key={c.id} className={`group flex items-center rounded-lg ${String(c.id) === id ? "bg-brand-soft" : "hover:bg-sunken"}`}>
              <Link to={`/app/ask/${c.id}`} onClick={() => setShowList(false)} className="min-w-0 flex-1 truncate px-3 py-2.5 text-sm" title={c.title}>{c.title}</Link>
              <button onClick={() => void del(c.id)} className="p-2 text-muted opacity-60 hover:text-bad group-hover:opacity-100" aria-label={`Delete conversation: ${c.title}`}><Trash2 className="h-4 w-4" aria-hidden /></button>
            </li>))}</ul>
        )}
      </aside>
      <section className="min-w-0">
        <PageHeader title="Ask a legal question" action={<button className="btn-ghost lg:hidden" onClick={() => setShowList(!showList)}><History className="h-4 w-4" aria-hidden />History</button>}>Describe what happened in your own words. Answers come only from the indexed legal sources.</PageHeader>
        {loadErr ? <ErrorBox error={loadErr} onRetry={() => nav(0)} /> : null}
        {msgs.length === 0 && !busy && !loadErr && (
          <Empty icon={<SearchX className="h-9 w-9" />} title="No question yet">Try something like "My landlord has not returned my security deposit after I vacated" or "A seller refuses to refund a defective product".</Empty>
        )}
        <div className="space-y-6" aria-live="polite">
          {msgs.map((m, i) => m.role === "user" ? (
            <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-4 py-3 text-paper" style={{ color: "rgb(250 247 242)" }}>{m.content}</div>
          ) : m.payload ? (
            <article key={i} className="card p-4 sm:p-5"><AnswerCard r={m.payload} onAsk={(x) => setQ(x)} /></article>
          ) : <article key={i} className="card p-4">{m.content}</article>)}
          {busy && <div className="card p-4"><Spinner label={`Searching the sources and checking citations… ${elapsed}s`} /><p className="mt-1 text-xs text-muted">The first request after start-up loads the models and can take longer.</p></div>}
          <div ref={end} />
        </div>
        {err ? <div className="mt-4"><ErrorBox error={err} onRetry={() => void send(q)} /></div> : null}
        <form onSubmit={submit} className="sticky bottom-0 mt-6 bg-paper pb-3 pt-2">
          {caseId && <p className="mb-1 text-xs text-muted">Asking within case #{caseId}</p>}
          <div className="flex items-end gap-2">
            <label htmlFor="q" className="sr-only">Your question</label>
            <textarea id="q" className="field min-h-[3.25rem] resize-y" rows={2} maxLength={4000} placeholder="What happened, when, and what do you want to know?" value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void send(q); } }} />
            <button className="btn-primary h-[3.25rem]" disabled={busy || q.trim().length < 5} aria-label="Send question"><SendHorizonal className="h-4 w-4" aria-hidden /></button>
          </div>
          <p className="mt-1 text-xs text-muted">Ctrl/⌘ + Enter to send · legal information, not legal advice.</p>
        </form>
      </section>
    </div>
  );
}
