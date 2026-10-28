import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.restoreAllMocks());
const respond = (status: number, body: unknown) => vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));

describe("api()", () => {
  it("sends the CSRF header and credentials", async () => {
    const spy = respond(200, { ok: true });
    await api("/api/x", { method: "POST", json: { a: 1 } });
    const [, init] = spy.mock.calls[0];
    expect((init!.headers as Headers).get("X-Requested-With")).toBe("nyaya");
    expect(init!.credentials).toBe("include");
    expect(init!.body).toBe('{"a":1}');
  });
  it("maps server error envelopes to ApiError", async () => {
    respond(503, { error: { code: "model_unavailable", message: "Model 'x' is unavailable" } });
    await expect(api("/api/x")).rejects.toMatchObject({ status: 503, code: "model_unavailable" });
  });
  it("keeps field-level validation errors", async () => {
    respond(422, { error: { code: "validation_error", message: "bad", fields: [{ field: "password", message: "too short" }] } });
    const e = (await api("/api/x").catch((x) => x)) as ApiError;
    expect(e).toBeInstanceOf(ApiError);
    expect(e.fields?.[0].field).toBe("password");
  });
  it("reports an unreachable backend in plain words", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(api("/api/x")).rejects.toMatchObject({ code: "network" });
  });
  it("handles 204 without a body", async () => { respond(204, null); await expect(api("/api/x", { method: "DELETE" })).resolves.toBeUndefined(); });
});
