import type { ReactNode } from "react";
import { Link } from "react-router-dom";

function Doc({ title, updated, children }: { title: string; updated?: string; children: ReactNode }) {
  return <article className="prose-legal mx-auto max-w-3xl px-4 py-12"><h1 className="text-4xl font-semibold">{title}</h1>{updated && <p className="mt-1 text-sm text-muted">{updated}</p>}<div className="mt-6 space-y-4 leading-relaxed [&_h2]:mt-8 [&_h2]:text-2xl [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_li]:py-0.5 [&_a]:text-brand [&_a]:underline">{children}</div></article>;
}

export function Trust() {
  return (
    <Doc title="How answers are produced" updated="Methodology — what is measured and what is not">
      <p>Nyaya Bharatha is a retrieval system with strict checks, not a chatbot that “knows” the law. Understanding the pipeline tells you how far to trust it.</p>
      <h2>1. Sources</h2>
      <p>Only documents ingested into this installation can be cited. Each keeps its title, identifier, authority, jurisdiction, dates, original URL, version and ingestion time. Statutes are loaded from official PDFs you supply (India Code, Gazette); Supreme Court judgments come from the public dataset built from the Court's own publications. The corpus is only as current as its last ingestion — it is <b>not</b> continuously updated.</p>
      <h2>2. Retrieval</h2>
      <ul>
        <li>Your question is normalised and lightly expanded with lay→legal vocabulary.</li>
        <li>Keyword search (BM25) and dense search run in parallel and are merged by reciprocal-rank fusion.</li>
        <li><b>InLegalBERT</b> and <b>InCaseLawBERT</b> (IIT Kharagpur) represent passages; <b>CustomInLawBERT</b> identifies the legal topic. These are pre-trained encoders without a sentence-embedding head, so we pool and centre their outputs and rely on the lexical component too. Measured results are in <code>docs/EVALUATION.md</code> in the repository.</li>
        <li>Repealed, not-yet-in-force or superseded provisions are excluded or flagged using only status information recorded at ingestion.</li>
      </ul>
      <h2>3. The answer</h2>
      <p>By default the answer is composed of <i>verbatim excerpts</i> from the retrieved passages, labelled as such. An optional local text-generation model can write a plain-language summary, but it is instructed to use only the retrieved passages and its output is checked afterwards. The four Law-AI models do not write answers.</p>
      <h2>4. Citation validation</h2>
      <p>Every citation marker, quotation and link in an answer is checked against the passages that were retrieved. Markers pointing nowhere, quotations not found in the cited passage, and links not recorded in a source are removed and reported. Statutory references in generated prose that do not appear in the retrieved text are flagged.</p>
      <h2>5. When it declines</h2>
      <p>If nothing retrieved shares real vocabulary with your question, you will be told the sources don't support an answer instead of getting a guess.</p>
      <h2>6. Translation</h2>
      <p>Translation uses <b>InLegalTrans-En2Indic-1B</b> and covers exactly: Bengali, Hindi, Marathi, Tamil, Telugu, Malayalam, Punjabi, Gujarati and Odia. Quality varies by language (the model card reports its lowest scores for Odia). Translations are never authoritative.</p>
      <h2>Limits you should know</h2>
      <ul>
        <li>This is legal information, not legal advice, and it cannot assess how a court will decide your matter.</li>
        <li>Coverage is limited to what has been ingested. Absence of a result does not mean absence of law.</li>
        <li>Document facts are pattern-matched and can be wrong or incomplete.</li>
      </ul>
      <p>Questions or corrections? See the <Link to="/terms">disclaimer</Link>.</p>
    </Doc>
  );
}

export function Privacy() {
  return (
    <Doc title="Privacy & data retention" updated="Applies to this self-hosted installation">
      <p>Legal questions and documents are sensitive. This notice explains what is stored and how to remove it. It describes the software's behaviour; it is not a claim of legal compliance.</p>
      <h2>What is stored</h2>
      <ul><li>Account: email, display name (optional) and a salted scrypt password hash.</li><li>Your questions and the structured answers.</li><li>Cases, drafts and draft revisions you create.</li><li>Uploaded files (under random names, in a per-user folder) and the text and facts extracted from them.</li><li>A security audit log of actions such as sign-in, upload and account deletion — without message text, document text or file names.</li></ul>
      <h2>What is not stored or sent</h2>
      <ul><li>Nothing is sent to external AI services: models run locally on the machine hosting the installation.</li><li>No advertising or behavioural-tracking scripts are included.</li><li>Document contents are not written to application logs.</li></ul>
      <h2>Retention and deletion</h2>
      <p>Data stays until you delete it. From Settings you can export everything and delete your account, which removes all your rows and uploaded files immediately. Database backups taken by whoever hosts the installation are outside the application's control.</p>
      <h2>Who can see it</h2>
      <p>Other users cannot: every private resource is checked against your account on the server. The person who hosts the installation can access its disk and database; choose a host you trust.</p>
      <h2>Indian data-protection law</h2>
      <p>The Digital Personal Data Protection Act, 2023 may impose duties (notice, consent, grievance redressal, retention limits) on whoever operates this service for others. Those obligations, including how they apply to legal-professional confidentiality, have <b>not</b> been assessed by the authors of this software; an operator must obtain their own advice before offering it to the public.</p>
    </Doc>
  );
}

export function Terms() {
  return (
    <Doc title="Disclaimer & terms of use">
      <p><b>Nyaya Bharatha provides legal information and drafting assistance. It is not a law firm and does not provide legal advice, legal opinions or representation.</b> Using it creates no advocate–client relationship and no privilege.</p>
      <ul>
        <li>Information may be incomplete, outdated or wrong. Always verify against official sources (India Code, the Gazette, court websites).</li>
        <li>Nothing here predicts the outcome of any case or guarantees that a generated document is correct, complete or acceptable to a court or authority.</li>
        <li>Drafts are never filed, served or submitted on your behalf. They are marked as drafts for review.</li>
        <li>Machine translations are not authoritative.</li>
        <li>Court filings, limitation periods and criminal matters need a qualified advocate. Free legal aid may be available: see the <Link to="/aid">directory</Link> or call NALSA on 15100.</li>
        <li>In an emergency call 112.</li>
      </ul>
      <p>Software is provided “as is” without warranty. The Law-AI models are published by their authors under the MIT licence; see the model cards linked on the <Link to="/status">status page</Link>.</p>
    </Doc>
  );
}
