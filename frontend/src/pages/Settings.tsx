import { useState } from "react";
import { Download, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, download } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Dialog, Field, PageHeader } from "../components/ui";
import { useToast } from "../lib/toast";

export default function Settings() {
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  async function exp() { try { const d = await api<object>("/api/auth/export"); download(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }), "nyaya-export.json"); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Export failed"); } }
  async function del() { try { await api("/api/auth/account", { method: "DELETE" }); window.location.assign("/"); } catch (e) { toast("error", e instanceof ApiError ? e.message : "Deletion failed"); nav(0); } }
  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings & privacy" />
      <section className="card space-y-1 p-4"><h2 className="font-semibold">Account</h2><p className="text-sm text-muted">{user?.display_name || "—"} · {user?.email}</p></section>
      <section className="card space-y-3 p-4"><h2 className="font-semibold">Your data</h2><p className="text-sm text-muted">Download everything stored about you — cases, conversations, extracted document data and drafts — as a JSON file. Uploaded files themselves are not included; your extracted text is.</p>
        <button className="btn-secondary" onClick={() => void exp()}><Download className="h-4 w-4" aria-hidden />Export my data</button></section>
      <section className="card space-y-3 p-4"><h2 className="font-semibold text-bad">Delete my account</h2><p className="text-sm text-muted">Permanently deletes your account, all cases, conversations, drafts, extracted data and the uploaded files from disk. This cannot be undone.</p>
        <button className="btn-danger" onClick={() => setOpen(true)}><Trash2 className="h-4 w-4" aria-hidden />Delete account…</button></section>
      <Alert>See the <Link className="underline" to="/privacy">privacy notice</Link> for what is stored, where, and for how long.</Alert>
      <Dialog open={open} title="Delete your account?" onClose={() => { setOpen(false); setTyped(""); }}>
        <p className="text-sm text-muted">Type <b>DELETE</b> to confirm. Everything you have stored will be removed immediately.</p>
        <Field label="Confirmation"><input className="field" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" /></Field>
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-danger" disabled={typed !== "DELETE"} onClick={() => void del()}>Delete everything</button></div>
      </Dialog>
    </div>
  );
}
