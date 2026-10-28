import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AnswerCard } from "./Ask";
import type { AskResponse } from "../lib/api";

vi.mock("../lib/api", async (orig) => ({ ...(await orig<typeof import("../lib/api")>()), api: vi.fn().mockResolvedValue({ translation_languages: { hi: "Hindi" } }) }));

const base: AskResponse = {
  status: "ok", question: "q", answer: '- Act — Section 3: "refund the price" [S1]', answer_mode: "extractive", answer_note: "verbatim excerpts",
  citations: [{ n: 1, title: "Consumer Act", doc_type: "statute", identifier: "Act 1", authority: "Parliament", jurisdiction: "India", ref: "Section 3", pages: [4, 4], url: "https://example.org/act", publication_date: null, status: "unknown", synthetic: false, version: "1", ingested_at: "2026-01-01T00:00:00Z", excerpt: "The seller shall refund the price.", warnings: [] }],
  citation_report: { total: 2, valid: 2, validity: 1, issues: [] }, topic: { topic: "consumer", confidence: "high", model: "law-ai/CustomInLawBERT", ranked: [] },
  retrieval: { components: ["bm25", "inlegalbert"], corpus_chunks: 10, skipped: {} }, sections: { uncertainties: ["May be incomplete"], next_steps: ["Keep receipts"], professional_advice: "See an advocate" },
  clarifying_questions: ["When did you buy it?"], urgent_contacts: [], disclaimer: "Not legal advice.", models_used: [], timings: { total_s: 1 },
};
const view = (r: AskResponse, onAsk = vi.fn()) => render(<MemoryRouter><AnswerCard r={r} onAsk={onAsk} /></MemoryRouter>);

describe("AnswerCard", () => {
  it("shows sources with pinpoint, verified-citation badge, uncertainty and disclaimer", () => {
    view(base);
    expect(screen.getByText("2/2 citations verified")).toBeInTheDocument();
    expect(screen.getByText(/Section 3 · p\. 4/)).toBeInTheDocument();
    expect(screen.getByText("May be incomplete")).toBeInTheDocument();
    expect(screen.getByText("Not legal advice.")).toBeInTheDocument();
    expect(screen.getByText("in-force status unverified")).toBeInTheDocument();
  });
  it("expanding a citation reveals the excerpt and the original-source link", () => {
    view(base);
    fireEvent.click(screen.getByRole("button", { name: /Consumer Act/ }));
    expect(screen.getByText("The seller shall refund the price.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open original source/ })).toHaveAttribute("href", "https://example.org/act");
  });
  it("never links to a synthetic source and labels it as not real law", () => {
    view({ ...base, citations: [{ ...base.citations[0], synthetic: true }] });
    expect(screen.getByText(/synthetic test data/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Consumer Act/ }));
    expect(screen.queryByRole("link", { name: /Open original source/ })).toBeNull();
  });
  it("declines honestly when evidence is insufficient (no sources, no fake answer)", () => {
    view({ ...base, status: "insufficient_evidence", answer: null, citations: [], message: "The indexed legal sources do not contain enough." });
    expect(screen.getByText(/don't support an answer/)).toBeInTheDocument();
    expect(screen.queryByText("Sources")).toBeNull();
  });
  it("surfaces urgent phone numbers as tel: links", () => {
    view({ ...base, urgent_contacts: [{ label: "National Cyber Crime Reporting Helpline", number: "1930" }] });
    expect(screen.getByRole("link", { name: /1930/ })).toHaveAttribute("href", "tel:1930");
  });
  it("clarifying questions feed back into the composer", () => {
    const onAsk = vi.fn(); view(base, onAsk);
    fireEvent.click(screen.getByRole("button", { name: "When did you buy it?" }));
    expect(onAsk).toHaveBeenCalledWith("When did you buy it?");
  });
});
