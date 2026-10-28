import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BookMarked, FileSearch, Languages, PenLine, ShieldCheck, Quote, ScrollText, Compass, AlertTriangle } from "lucide-react";
import { api, type SystemStatus } from "../lib/api";
import { useAuth } from "../lib/auth";

function LiveStrip() {
  const [s, setS] = useState<SystemStatus | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api<SystemStatus>("/api/system/status").then(setS).catch(() => setFailed(true)); }, []);
  const real = s?.corpus.sources.filter((x) => !x.synthetic) ?? [];
  const n = (t: string) => real.filter((x) => x.doc_type === t).reduce((a, b) => a + b.count, 0);
  const ready = s?.models.filter((m) => m.downloaded && m.kind !== "generator").length ?? 0;
  const items = s ? [
    [String(n("statute")), "statutes & rules indexed"], [String(n("judgment")), "judgments indexed"], [String(s.corpus.chunks), "citable passages"],
    [`${ready} of 4`, "Law-AI models installed"], [String(Object.keys(s.translation_languages).length), "translation languages"],
  ] : [];
  return (
    <section aria-label="This installation right now" className="border-y border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-10 gap-y-3 px-4 py-4 text-sm">
        <span className="chip">{failed ? "Backend not reachable" : s ? "Live from this installation" : "Loading…"}</span>
        {items.map(([v, l]) => <span key={l}><b className="font-display text-xl">{v}</b> <span className="text-muted">{l}</span></span>)}
        {s && n("statute") === 0 && <span className="text-warn">No statutes ingested yet — see the ingestion guide.</span>}
      </div>
    </section>
  );
}

const Bar = ({ w, strong }: { w: string; strong?: boolean }) => <span className={`block h-2 rounded-full ${strong ? "bg-ink/60" : "bg-line"}`} style={{ width: w }} />;

function AnswerAnatomy() {
  const Row = ({ n, title, children }: { n: string; title: string; children: React.ReactNode }) => (
    <li className="grid grid-cols-[2rem_1fr] gap-3 border-t border-line py-3 first:border-0"><span className="font-display text-lg text-brass">{n}</span><div className="space-y-1.5"><p className="text-sm font-semibold">{title}</p>{children}</div></li>
  );
  return (
    <figure className="card rise p-5 shadow-card" aria-label="Layout of every answer">
      <figcaption className="mb-2 flex items-center justify-between text-xs text-muted"><span className="font-semibold uppercase tracking-wider">How every answer is laid out</span><span>schematic · no sample law shown</span></figcaption>
      <ol>
        <Row n="1" title="Passages from the sources"><Bar w="96%" strong /><Bar w="88%" /><Bar w="62%" /></Row>
        <Row n="2" title="Citations you can open"><div className="flex flex-wrap gap-1.5"><span className="chip">[S1] Act · Section</span><span className="chip">[S2] Judgment · ¶ · p.</span></div></Row>
        <Row n="3" title="What we are unsure about"><Bar w="80%" /><Bar w="45%" /></Row>
        <Row n="4" title="Questions that would change the answer"><Bar w="70%" /></Row>
        <Row n="5" title="Practical next steps & when to see a lawyer"><Bar w="90%" /><Bar w="55%" /></Row>
      </ol>
    </figure>
  );
}

const caps = [
  { icon: Quote, t: "Ask in plain language", d: "Describe your situation. You get passages from indexed Indian legal sources, with pinpoint references, a statement of what is uncertain, and the facts that would change the answer. If the sources don't support an answer, it says so." },
  { icon: BookMarked, t: "Search the legal library", d: "Hybrid keyword and Law-AI encoder search over ingested statutes and Supreme Court judgments, with filters for type, year and whether a provision is in force on a given date." },
  { icon: FileSearch, t: "Analyse your documents", d: "Upload a PDF, Word file or text. Dates, amounts, parties, clauses and obligations are extracted with page references, and possible inconsistencies across documents are flagged for you to check." },
  { icon: PenLine, t: "Prepare drafts you can edit", d: "Legal notices, consumer complaints, police complaints and recovery plaints from structured facts. Missing facts are marked, authorities are checked against the corpus, and you export to Word." },
  { icon: Languages, t: "Read it in your language", d: "Machine translation of explanations into nine Indian languages using a legal-domain model — always labelled as a translation, never as the authoritative text." },
  { icon: Compass, t: "Find free legal aid", d: "A directory of NALSA and State Legal Services Authorities with helplines, eligibility notes and the date each entry was last verified." },
];

const steps = [
  ["Tell us what happened", "Your question or a document. Urgent situations surface emergency numbers first."],
  ["We search the indexed sources", "Keyword and encoder retrieval, filtered by type, date and in-force status."],
  ["Every claim is checked", "Citations, quotations and links are validated against the passages that were retrieved."],
  ["You decide the next step", "Next steps, open questions and a prompt to involve an advocate when it matters."],
];

const models = [
  ["InLegalBERT", "Represents statute and provision passages for retrieval", "law-ai/InLegalBERT"],
  ["InCaseLawBERT", "Represents judgment passages for case-law retrieval", "law-ai/InCaseLawBERT"],
  ["CustomInLawBERT", "Identifies the legal topic of a question", "law-ai/CustomInLawBERT"],
  ["InLegalTrans-En2Indic-1B", "Translates explanations into nine Indian languages", "law-ai/InLegalTrans-En2Indic-1B"],
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-12 md:grid-cols-[1.15fr_1fr] md:pt-20">
        <div className="space-y-6">
          <p className="chip !border-brass/40 !bg-brass-soft !text-brass">Indian legal information · grounded in sources</p>
          <h1 className="text-balance text-4xl font-semibold leading-[1.08] sm:text-5xl md:text-6xl">Find out what the law says. Then decide what to do.</h1>
          <p className="max-w-xl text-lg leading-relaxed text-muted">Ask a question, search statutes and Supreme Court judgments, check your documents and prepare drafts — with every answer tied to a source you can open, and clear about what it doesn't know.</p>
          <div className="flex flex-wrap gap-3">
            <Link to={user ? "/app/ask" : "/register"} className="btn-primary">{user ? "Ask a question" : "Create a free account"}<ArrowRight className="h-4 w-4" aria-hidden /></Link>
            <Link to="/library" className="btn-secondary">Search the library — no sign-in</Link>
          </div>
          <p className="flex max-w-xl items-start gap-2 text-sm text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />Runs on local open models. Your documents stay on the machine hosting this installation.</p>
        </div>
        <AnswerAnatomy />
      </section>

      <LiveStrip />

      <section className="mx-auto max-w-6xl px-4 py-16" aria-labelledby="cap">
        <h2 id="cap" className="max-w-2xl text-3xl font-semibold md:text-4xl">What you can do here</h2>
        <ul className="mt-8 divide-y divide-line border-y border-line">
          {caps.map(({ icon: I, t, d }) => (
            <li key={t} className="grid gap-3 py-6 md:grid-cols-[18rem_1fr] md:gap-10"><h3 className="flex items-center gap-3 text-xl font-semibold"><I className="h-5 w-5 text-brass" aria-hidden />{t}</h3><p className="leading-relaxed text-muted">{d}</p></li>
          ))}
        </ul>
      </section>

      <section className="bg-sunken py-16" aria-labelledby="how">
        <div className="mx-auto max-w-6xl px-4">
          <h2 id="how" className="text-3xl font-semibold md:text-4xl">How it works</h2>
          <ol className="mt-8 grid gap-6 md:grid-cols-4">
            {steps.map(([t, d], i) => (<li key={t} className="border-t-2 border-brand pt-4"><span className="font-display text-3xl text-brass">{i + 1}</span><h3 className="mt-1 text-lg font-semibold">{t}</h3><p className="mt-1 text-sm leading-relaxed text-muted">{d}</p></li>))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16" aria-labelledby="trust">
        <div className="grid gap-10 md:grid-cols-2">
          <div>
            <h2 id="trust" className="text-3xl font-semibold md:text-4xl">Honest about its limits</h2>
            <ul className="mt-6 space-y-4">
              {[["It declines instead of guessing.", "When the indexed sources don't cover your question, you get that message, not a confident-sounding answer."],
                ["No invented citations.", "Markers, quotations and links that can't be traced to a retrieved passage are removed and reported."],
                ["Dates and status matter.", "Repealed or not-yet-in-force provisions are filtered out unless you search history, and unverified status is flagged."],
                ["Translations are not the law.", "Machine translations are labelled; only the official publication is authoritative."]].map(([a, b]) => (
                <li key={a} className="flex gap-3"><ScrollText className="mt-1 h-4 w-4 shrink-0 text-brass" aria-hidden /><p><b>{a}</b> <span className="text-muted">{b}</span></p></li>))}
            </ul>
            <p className="mt-6 flex items-start gap-2 rounded-lg bg-warn-soft p-3 text-sm text-warn"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />This is legal information, not legal advice. For deadlines, filings and anything consequential, speak to a qualified advocate.</p>
          </div>
          <div>
            <h3 className="text-xl font-semibold">The four Law-AI models, and what each is used for</h3>
            <p className="mt-1 text-sm text-muted">These are encoders and a translator. They retrieve and translate; they do not write the answer.</p>
            <table className="mt-4 w-full text-left text-sm"><caption className="sr-only">Models and roles</caption>
              <thead><tr className="border-b border-line text-muted"><th scope="col" className="py-2 pr-3 font-medium">Model</th><th scope="col" className="py-2 font-medium">Role</th></tr></thead>
              <tbody>{models.map(([n, r, id]) => (<tr key={n} className="border-b border-line align-top"><td className="py-3 pr-3"><a className="font-semibold text-brand underline-offset-2 hover:underline" href={`https://huggingface.co/${id}`} target="_blank" rel="noreferrer">{n}</a></td><td className="py-3 text-muted">{r}</td></tr>))}</tbody>
            </table>
            <Link to="/trust" className="btn-ghost mt-3 !px-0">Read the full methodology<ArrowRight className="h-4 w-4" aria-hidden /></Link>
          </div>
        </div>
      </section>

      <section className="bg-brand text-paper"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-12">
        <h2 className="max-w-xl text-3xl font-semibold" style={{ color: "rgb(250 247 242)" }}>Start with the question you actually have.</h2>
        <Link to={user ? "/app/ask" : "/register"} className="btn bg-paper text-brand hover:opacity-90" style={{ background: "rgb(250 247 242)", color: "rgb(31 58 95)" }}>{user ? "Ask a question" : "Create a free account"}<ArrowRight className="h-4 w-4" aria-hidden /></Link>
      </div></section>
    </>
  );
}
