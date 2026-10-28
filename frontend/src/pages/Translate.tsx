import { useEffect, useState } from "react";
import { Copy } from "lucide-react";
import { api, type SystemStatus } from "../lib/api";
import { Alert, ErrorBox, Field, PageHeader, Spinner } from "../components/ui";
import { useToast } from "../lib/toast";

export default function Translate() {
  const toast = useToast();
  const [langs, setLangs] = useState<Record<string, string>>({});
  const [model, setModel] = useState<SystemStatus["models"][number] | null>(null);
  const [text, setText] = useState("");
  const [lang, setLang] = useState("hi");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [out, setOut] = useState<{ translation: string; language: string; disclaimer: string; seconds: number; sentences: number } | null>(null);
  useEffect(() => { api<SystemStatus>("/api/system/status").then((s) => { setLangs(s.translation_languages); setModel(s.models.find((m) => m.key === "inlegaltrans") ?? null); }).catch(setErr); }, []);
  async function go() { setBusy(true); setErr(null); setOut(null); try { setOut(await api("/api/translate", { method: "POST", json: { text, target: lang } })); } catch (e) { setErr(e); } finally { setBusy(false); } }
  return (
    <div className="max-w-3xl">
      <PageHeader title="Translate English legal text">Uses law-ai/InLegalTrans-En2Indic-1B, a legal-domain English→Indic model. It supports exactly these nine target languages and no others.</PageHeader>
      <div className="space-y-4">
        {model && !model.downloaded && <Alert kind="warn" title="Translation model not installed">Run <code>python -m app.cli download-models --only inlegaltrans</code> (about {Math.round(model.approx_disk_mb / 1000)} GB) and restart.</Alert>}
        <Alert>Machine translation is for understanding only. It is not the authoritative text of any law or judgment. The first translation after start-up loads a ~4 GB model and can take a minute.</Alert>
        <Field label="English text" help={`${text.length}/8000 characters`}><textarea className="field min-h-[9rem]" maxLength={8000} value={text} onChange={(e) => setText(e.target.value)} /></Field>
        <div className="flex flex-wrap items-end gap-3"><Field label="Translate into"><select className="field" value={lang} onChange={(e) => setLang(e.target.value)}>{Object.entries(langs).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></Field>
          <button className="btn-primary" onClick={go} disabled={busy || !text.trim()}>{busy ? <Spinner label="Translating…" /> : "Translate"}</button></div>
        {err ? <ErrorBox error={err} onRetry={go} /> : null}
        {out && (<section className="card space-y-2 p-4" aria-live="polite"><div className="flex items-center justify-between"><h2 className="font-semibold">{out.language}</h2><button className="btn-ghost" onClick={() => { void navigator.clipboard.writeText(out.translation); toast("ok", "Copied"); }}><Copy className="h-4 w-4" aria-hidden />Copy</button></div>
          <p className="indic whitespace-pre-wrap text-lg">{out.translation}</p><p className="text-xs text-muted">{out.sentences} sentence(s) · {out.seconds}s · {out.disclaimer}</p></section>)}
      </div>
    </div>
  );
}
