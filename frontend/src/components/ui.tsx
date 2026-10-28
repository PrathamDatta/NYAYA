import { useEffect, useRef, type ReactNode } from "react";
import { AlertTriangle, Info, Loader2, RotateCw } from "lucide-react";
import { ApiError } from "../lib/api";

export function Spinner({ label }: { label?: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-muted" role="status"><Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden />{label}</span>;
}

export function Alert({ kind = "info", title, children }: { kind?: "info" | "warn" | "error" | "ok"; title?: string; children: ReactNode }) {
  const cls = { info: "bg-brand-soft text-brand-strong", warn: "bg-warn-soft text-warn", error: "bg-bad-soft text-bad", ok: "bg-ok-soft text-ok" }[kind];
  const Icon = kind === "info" || kind === "ok" ? Info : AlertTriangle;
  return (
    <div className={`flex gap-3 rounded-lg p-3.5 text-sm ${cls}`} role={kind === "error" ? "alert" : undefined}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">{title && <p className="font-semibold">{title}</p>}<div className="leading-relaxed">{children}</div></div>
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  const unavailable = error instanceof ApiError && error.code === "model_unavailable";
  return (
    <Alert kind="error" title={unavailable ? "A required model is not available" : "That didn't work"}>
      <p>{msg}</p>
      {onRetry && <button onClick={onRetry} className="mt-2 inline-flex items-center gap-1.5 font-semibold underline"><RotateCw className="h-3.5 w-3.5" aria-hidden />Try again</button>}
    </Alert>
  );
}

export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line px-6 py-12 text-center">
      <div className="mb-3 text-muted" aria-hidden>{icon}</div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "bad" | "brand"; children: ReactNode }) {
  const cls = { neutral: "bg-sunken text-muted", ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", brand: "bg-brand-soft text-brand-strong" }[tone];
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{children}</span>;
}

export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const d = ref.current; if (!d) return; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); }, [open]);
  return (
    <dialog ref={ref} onClose={onClose} onCancel={onClose} aria-labelledby="dlg-title" className="w-[min(92vw,28rem)] rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40">
      <div className="space-y-4 p-6"><h2 id="dlg-title" className="text-xl font-semibold">{title}</h2>{children}</div>
    </dialog>
  );
}

export function PageHeader({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-3xl font-semibold">{title}</h1>{children && <p className="mt-1 max-w-2xl text-muted">{children}</p>}</div>
      {action}
    </header>
  );
}

export function Field({ label, help, error, children }: { label: string; help?: string; error?: string; children: ReactNode }) {
  return (
    <label className="block"><span className="label">{label}</span>{children}
      {help && <span className="mt-1 block text-xs text-muted">{help}</span>}
      {error && <span className="mt-1 block text-xs font-medium text-bad" role="alert">{error}</span>}
    </label>
  );
}

export const fmtDate = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");
export const fmtBytes = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
export const docTypeLabel = (t: string) => ({ statute: "Statute", judgment: "Judgment", rule: "Rule", notification: "Notification", synthetic: "Test fixture" }[t] ?? t);
