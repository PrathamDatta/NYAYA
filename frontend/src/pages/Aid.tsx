import { useEffect, useState } from "react";
import { ExternalLink, Mail, MapPin, Phone, Search } from "lucide-react";
import { api, type AidEntry } from "../lib/api";
import { Alert, Badge, Empty, ErrorBox, PageHeader, Spinner, fmtDate } from "../components/ui";

export default function Aid() {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [data, setData] = useState<{ items: AidEntry[]; provenance: string } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { const t = setTimeout(() => { const p = new URLSearchParams({ q, kind }); api<typeof data>(`/api/aid/directory?${p}`).then(setData).catch(setErr); }, 200); return () => clearTimeout(t); }, [q, kind]);
  return (
    <div>
      <PageHeader title="Free legal aid">Under the Legal Services Authorities Act, 1987, eligible people can get a free lawyer. Start with the national helpline or your State authority.</PageHeader>
      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        {[["Emergency (police)", "112"], ["NALSA legal aid helpline", "15100"], ["Women helpline", "181"]].map(([l, n]) => <a key={n} href={`tel:${n}`} className="card flex items-center justify-between p-3 hover:border-brand"><span className="text-sm text-muted">{l}</span><b className="inline-flex items-center gap-1.5 font-display text-xl"><Phone className="h-4 w-4 text-brass" aria-hidden />{n}</b></a>)}
      </div>
      {data && <Alert kind="warn" title="Check before you call">{data.provenance}</Alert>}
      <div className="my-4 flex flex-wrap gap-2"><div className="relative min-w-[16rem] flex-1"><Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted" aria-hidden /><input className="field !pl-9" placeholder="Search by state, authority or service" aria-label="Search directory" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="field !w-auto" aria-label="Type" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All</option><option value="national">National</option><option value="state">State</option></select></div>
      {err ? <ErrorBox error={err} /> : null}
      {!data && !err && <Spinner label="Loading…" />}
      {data && data.items.length === 0 && <Empty icon={<Search className="h-9 w-9" />} title="No match">Try a state name such as “Karnataka”, or clear the filter.</Empty>}
      <ul className="space-y-3">{data?.items.map((a) => (
        <li key={a.id} className="card p-4"><div className="flex flex-wrap items-start justify-between gap-2"><h2 className="text-lg font-semibold leading-snug">{a.name}</h2><Badge tone={a.type === "national" ? "brand" : "neutral"}>{a.stateOrUT}</Badge></div>
          <p className="mt-1 text-sm text-muted">{a.serviceDescription}</p>
          <ul className="mt-2 list-disc pl-5 text-sm">{a.eligibilityCriteria.map((e) => <li key={e}>{e}</li>)}</ul>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {a.helpline && <a className="inline-flex items-center gap-1.5 font-semibold" href={`tel:${a.helpline}`}><Phone className="h-4 w-4 text-brass" aria-hidden />Helpline {a.helpline}</a>}
            {a.contactPhone && <a className="inline-flex items-center gap-1.5" href={`tel:${a.contactPhone.replace(/[^+\d]/g, "")}`}><Phone className="h-4 w-4 text-muted" aria-hidden />{a.contactPhone}</a>}
            {a.email && <a className="inline-flex items-center gap-1.5" href={`mailto:${a.email}`}><Mail className="h-4 w-4 text-muted" aria-hidden />{a.email}</a>}
            {a.website && <a className="inline-flex items-center gap-1.5 font-semibold text-brand" href={a.website} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" aria-hidden />Official website</a>}</div>
          {a.address && <p className="mt-2 flex items-start gap-1.5 text-sm text-muted"><MapPin className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{a.address}</p>}
          <p className="mt-2 text-xs text-warn">Last verified {fmtDate(a.lastVerifiedDate)} — details may have changed.</p></li>))}</ul>
    </div>
  );
}
