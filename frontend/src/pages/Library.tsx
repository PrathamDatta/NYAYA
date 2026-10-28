import { useEffect, useState, type FormEvent } from "react";
import { ExternalLink, FileSearch, Library as LibIcon, Search } from "lucide-react";
import { api, type Hit, type Source } from "../lib/api";
import { Alert, Badge, Empty, ErrorBox, PageHeader, Spinner, docTypeLabel, fmtDate } from "../components/ui";

export default function Library() {
  const [tab, setTab] = useState<"search" | "browse">("search");
  const [q, setQ] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [yf, setYf] = useState("");
  const [yt, setYt] = useState("");
  const [hist, setHist] = useState(false);
  const [res, setRes] = useState<{ results: Hit[]; info: { components: string[]; corpus_chunks: number; skipped: Record<string, string>; excluded_by_validity?: Record<string, string> } } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [src, setSrc] = useState<{ items: Source[]; total: number } | null>(null);
  const [page, setPage] = useState(1);
  const [bq, setBq] = useState("");

  async function search(e?: FormEvent) {
    e?.preventDefault(); if (q.trim().length < 2) return;
    setBusy(true); setErr(null);
    const p = new URLSearchParams({ q, include_historical: String(hist) });
    types.forEach((t) => p.append("doc_type", t)); if (yf) p.set("year_from", yf); if (yt) p.set("year_to", yt);
    try { setRes(await api(`/api/library/search?${p}`)); } catch (x) { setErr(x); } finally { setBusy(false); }
  }
  useEffect(() => {
    if (tab !== "browse") return;
    const p = new URLSearchParams({ page: String(page), page_size: "15" }); if (bq) p.set("q", bq);
    api<{ items: Source[]; total: number }>(`/api/library/sources?${p}`).then(setSrc).catch(setErr);
  }, [tab, page, bq]);
  const toggle = (t: string) => setTypes((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]));

  return (
    <div>
      <PageHeader title="Legal library">Search ingested statutes and judgments. Results combine keyword matching with Law-AI encoder similarity, and respect in-force dates.</PageHeader>
      <div role="tablist" aria-label="Library views" className="mb-5 inline-flex rounded-lg border border-line bg-surface p-1">
        {(["search", "browse"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`rounded-md px-4 py-2 text-sm font-semibold ${tab === t ? "bg-brand-soft text-brand-strong" : "text-muted"}`}>{t === "search" ? "Search passages" : "Browse sources"}</button>)}
      </div>
      {tab === "search" ? (
        <>
          <form onSubmit={search} className="card space-y-4 p-4">
            <div className="flex gap-2"><label htmlFor="lq" className="sr-only">Search</label><input id="lq" className="field" placeholder="e.g. return of security deposit, cheating, right to be heard" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} /><button className="btn-primary" disabled={busy || q.trim().length < 2}><Search className="h-4 w-4" aria-hidden />Search</button></div>
            <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm"><legend className="sr-only">Filters</legend>
              {[["statute", "Statutes"], ["judgment", "Judgments"], ["rule", "Rules"], ["notification", "Notifications"]].map(([k, l]) => <label key={k} className="inline-flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={types.includes(k)} onChange={() => toggle(k)} />{l}</label>)}
              <label className="inline-flex items-center gap-2">From <input className="field !w-24" inputMode="numeric" placeholder="year" value={yf} onChange={(e) => setYf(e.target.value.replace(/\D/g, "").slice(0, 4))} aria-label="From year" /></label>
              <label className="inline-flex items-center gap-2">To <input className="field !w-24" inputMode="numeric" placeholder="year" value={yt} onChange={(e) => setYt(e.target.value.replace(/\D/g, "").slice(0, 4))} aria-label="To year" /></label>
              <label className="inline-flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={hist} onChange={(e) => setHist(e.target.checked)} />Include repealed / historical</label>
            </fieldset>
          </form>
          <div className="mt-5 space-y-3" aria-live="polite">
            {busy && <Spinner label="Searching…" />}
            {err ? <ErrorBox error={err} onRetry={() => void search()} /> : null}
            {res && !busy && res.results.length === 0 && (
              <Empty icon={<FileSearch className="h-9 w-9" />} title={res.info.corpus_chunks ? "No matching passages" : "The corpus is empty"}>{res.info.corpus_chunks ? "Try different words, widen the year range, or include historical sources." : "No legal sources have been ingested into this installation yet. See the ingestion guide in the documentation."}</Empty>
            )}
            {res && Object.keys(res.info.skipped).length > 0 && <Alert kind="warn" title="Some retrieval models were unavailable">Showing results from the remaining components. {Object.entries(res.info.skipped).map(([k, v]) => `${k}: ${v}`).join(" · ")}</Alert>}
            {res?.results.map((h) => (
              <article key={h.chunk_id} className="card p-4">
                <div className="flex flex-wrap items-center gap-2"><Badge tone="brand">{docTypeLabel(h.source.doc_type)}</Badge><h2 className="text-base font-semibold leading-snug">{h.source.title}</h2></div>
                <p className="mt-1 text-xs text-muted">{h.ref_label}{h.page_start ? ` · p. ${h.page_start}${h.page_end && h.page_end !== h.page_start ? `–${h.page_end}` : ""}` : ""} · {h.source.identifier} · {fmtDate(h.source.publication_date)}</p>
                <p className="mt-2 text-sm leading-relaxed">{h.text.length > 600 ? h.text.slice(0, 600) + "…" : h.text}</p>
                {h.warnings.map((w) => <p key={w} className="mt-1 text-xs text-warn">{w}</p>)}
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted"><span>matched by {Object.keys(h.ranks).join(" + ")}</span>
                  {h.source.source_url && !h.source.is_synthetic && <a className="inline-flex items-center gap-1 font-semibold text-brand hover:underline" href={h.source.source_url} target="_blank" rel="noreferrer">Original source<ExternalLink className="h-3 w-3" aria-hidden /></a>}</div>
              </article>))}
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <input className="field max-w-md" placeholder="Filter sources by title or citation" aria-label="Filter sources" value={bq} onChange={(e) => { setBq(e.target.value); setPage(1); }} />
          {err ? <ErrorBox error={err} /> : null}
          {!src ? <Spinner label="Loading…" /> : src.items.length === 0 ? <Empty icon={<LibIcon className="h-9 w-9" />} title="No sources">Nothing matches, or no real sources have been ingested yet.</Empty> : (
            <>
              <p className="text-sm text-muted">{src.total} source{src.total === 1 ? "" : "s"}</p>
              <ul className="divide-y divide-line rounded-xl border border-line bg-surface">{src.items.map((s) => (
                <li key={s.id} className="flex flex-wrap items-start justify-between gap-2 p-4"><div className="min-w-0"><p className="font-medium leading-snug">{s.title}</p><p className="mt-1 text-xs text-muted">{docTypeLabel(s.doc_type)} · {s.identifier} · {s.authority} · {fmtDate(s.publication_date)}</p></div>
                  {s.source_url && <a className="inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" href={s.source_url} target="_blank" rel="noreferrer">Original<ExternalLink className="h-3.5 w-3.5" aria-hidden /></a>}</li>))}</ul>
              <div className="flex items-center justify-between"><button className="btn-secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><span className="text-sm text-muted">Page {page} of {Math.max(1, Math.ceil(src.total / 15))}</span><button className="btn-secondary" disabled={page * 15 >= src.total} onClick={() => setPage(page + 1)}>Next</button></div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
