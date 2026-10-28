import { useEffect, useState } from "react";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { api, type SystemStatus } from "../lib/api";
import { Alert, Badge, ErrorBox, PageHeader, Spinner, docTypeLabel } from "../components/ui";

export default function Status() {
  const [s, setS] = useState<SystemStatus | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api<SystemStatus>("/api/system/status").then(setS).catch(setErr); }, []);
  if (err) return <ErrorBox error={err} onRetry={() => location.reload()} />;
  if (!s) return <Spinner label="Loading…" />;
  return (
    <div className="space-y-8">
      <PageHeader title="System status">What this installation actually has — models, corpus and limits. Nothing here is simulated.</PageHeader>
      <section aria-labelledby="m"><h2 id="m" className="mb-2 text-xl font-semibold">Models</h2>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface"><table className="w-full min-w-[40rem] text-left text-sm"><thead className="bg-sunken text-muted"><tr>{["Model", "Pinned revision", "Role", "Disk / RAM (approx.)", "State"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>{s.models.map((m) => <tr key={m.key} className="border-t border-line align-top"><td className="px-3 py-2"><a className="font-semibold text-brand hover:underline" href={`https://huggingface.co/${m.repo_id}`} target="_blank" rel="noreferrer">{m.repo_id}</a></td><td className="px-3 py-2 font-mono text-xs">{m.revision.slice(0, 10)}</td><td className="px-3 py-2 text-muted">{m.role}</td><td className="px-3 py-2">{(m.approx_disk_mb / 1000).toFixed(1)} GB / {(m.approx_ram_mb / 1000).toFixed(1)} GB</td>
            <td className="px-3 py-2">{m.downloaded ? <span className="inline-flex items-center gap-1 text-ok"><CheckCircle2 className="h-4 w-4" aria-hidden />{m.loaded ? "installed · in memory" : "installed"}</span> : <span className="inline-flex items-center gap-1 text-warn"><CircleDashed className="h-4 w-4" aria-hidden />not downloaded</span>}</td></tr>)}</tbody></table></div>
        <p className="mt-2 text-xs text-muted">Device: {s.device} · answer generator: <b>{s.generator_backend}</b>{s.generator_backend === "extractive" ? " (quotes retrieved passages; no free-text generation)" : ""}</p>
      </section>
      <section aria-labelledby="c"><h2 id="c" className="mb-2 text-xl font-semibold">Legal corpus</h2>
        {s.corpus.chunks === 0 ? <Alert kind="warn" title="The corpus is empty">Answers will decline until sources are ingested.</Alert> : <ul className="flex flex-wrap gap-2">{s.corpus.sources.map((x, i) => <li key={i}><Badge tone={x.synthetic ? "bad" : "brand"}>{x.count} {x.synthetic ? "synthetic test " : ""}{docTypeLabel(x.doc_type).toLowerCase()}{x.count === 1 ? "" : "s"}</Badge></li>)}<li><Badge>{s.corpus.chunks} passages</Badge></li></ul>}
        {!s.corpus.sources.some((x) => x.doc_type === "statute" && !x.synthetic) && <p className="mt-2 text-sm text-warn">No statutes are ingested: Acts must be loaded from official India Code PDFs (see docs/INGESTION.md).</p>}
      </section>
      <section aria-labelledby="l"><h2 id="l" className="mb-2 text-xl font-semibold">Limits</h2><p className="text-sm text-muted">Uploads up to {s.limits.max_upload_mb} MB and {s.limits.max_pages} pages. Translation supports: {Object.values(s.translation_languages).join(", ")}.</p></section>
    </div>
  );
}
