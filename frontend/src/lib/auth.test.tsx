import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppLayout } from "../components/Layout";
import { AuthProvider } from "./auth";

afterEach(() => vi.restoreAllMocks());
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const app = () => render(<MemoryRouter initialEntries={["/app/ask"]}><AuthProvider><Routes><Route path="app" element={<AppLayout />}><Route path="ask" element={<p>workspace</p>} /></Route><Route path="login" element={<p>login page</p>} /></Routes></AuthProvider></MemoryRouter>);

describe("session handling", () => {
  it("a 401 sends the visitor to sign in", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(401, { error: { code: "unauthorized", message: "Please sign in." } }));
    app();
    expect(await screen.findByText("login page")).toBeInTheDocument();
  });
  it("a rate-limit (429) does NOT look like a logout: it shows a retry that recovers", async () => {
    const f = vi.spyOn(globalThis, "fetch");
    f.mockResolvedValueOnce(json(429, { error: { code: "rate_limited", message: "Too many requests." } }));
    f.mockResolvedValueOnce(json(200, { id: 1, email: "a@b.co", display_name: "", role: "user" }));
    app();
    expect(await screen.findByText("Too many requests.")).toBeInTheDocument();
    expect(screen.queryByText("login page")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(screen.getByText("workspace")).toBeInTheDocument());
  });
  it("an unreachable backend shows an explanation, not the login page", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    app();
    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument();
  });
});
