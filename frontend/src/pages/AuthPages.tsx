import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Field, Spinner } from "../components/ui";

function Shell({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return <div className="mx-auto max-w-md px-4 py-14"><h1 className="text-3xl font-semibold">{title}</h1><p className="mb-6 mt-1 text-muted">{sub}</p><div className="card p-6">{children}</div></div>;
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { await login(email, pw); nav((loc.state as { from?: string } | null)?.from ?? "/app/ask", { replace: true }); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Could not sign in."); } finally { setBusy(false); }
  }
  return (
    <Shell title="Sign in" sub="Welcome back.">
      <form onSubmit={submit} className="space-y-4">
        {err && <Alert kind="error">{err}</Alert>}
        <Field label="Email"><input className="field" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input className="field" type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner label="Signing in…" /> : "Sign in"}</button>
        <p className="text-center text-sm text-muted">New here? <Link className="font-semibold text-brand" to="/register">Create an account</Link></p>
      </form>
    </Shell>
  );
}

export function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", pw: "" });
  const [err, setErr] = useState<ApiError | string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await register(f.email, f.pw, f.name); nav("/app/ask", { replace: true }); }
    catch (x) { setErr(x instanceof ApiError ? x : "Could not create the account."); } finally { setBusy(false); }
  }
  const fe = (n: string) => (err instanceof ApiError ? err.fields?.find((x) => x.field === n)?.message : undefined);
  return (
    <Shell title="Create your account" sub="We collect only what's needed to keep your work private.">
      <form onSubmit={submit} className="space-y-4">
        {err && <Alert kind="error">{typeof err === "string" ? err : err.fields?.length ? "Please fix the highlighted fields." : err.message}</Alert>}
        <Field label="Name (optional)"><input className="field" autoComplete="name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Email" error={fe("email")}><input className="field" type="email" autoComplete="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Password" help="At least 10 characters." error={fe("password")}><input className="field" type="password" autoComplete="new-password" required minLength={10} value={f.pw} onChange={(e) => setF({ ...f, pw: e.target.value })} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner label="Creating…" /> : "Create account"}</button>
        <p className="text-center text-xs text-muted">By continuing you accept the <Link className="underline" to="/terms">disclaimer & terms</Link> and <Link className="underline" to="/privacy">privacy notice</Link>.</p>
        <p className="text-center text-sm text-muted">Already registered? <Link className="font-semibold text-brand" to="/login">Sign in</Link></p>
      </form>
    </Shell>
  );
}
