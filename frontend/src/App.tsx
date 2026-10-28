import { Link, Route, Routes } from "react-router-dom";
import { AppLayout, PublicLayout } from "./components/Layout";
import { Empty } from "./components/ui";
import Landing from "./pages/Landing";
import { Login, Register } from "./pages/AuthPages";
import Ask from "./pages/Ask";
import Library from "./pages/Library";
import Documents, { DocumentDetail } from "./pages/Documents";
import Drafts, { DraftEditor } from "./pages/Drafts";
import Cases, { CaseDetail } from "./pages/Cases";
import Translate from "./pages/Translate";
import Aid from "./pages/Aid";
import Settings from "./pages/Settings";
import Status from "./pages/Status";
import { Privacy, Terms, Trust } from "./pages/Static";
import { SearchX } from "lucide-react";

function NotFound() {
  return <div className="mx-auto max-w-xl px-4 py-20"><Empty icon={<SearchX className="h-10 w-10" />} title="Page not found" action={<Link to="/" className="btn-primary">Go home</Link>}>That address doesn't exist. Check the link or head back to the start.</Empty></div>;
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="library" element={<div className="mx-auto max-w-5xl px-4 py-8"><Library /></div>} />
        <Route path="aid" element={<div className="mx-auto max-w-5xl px-4 py-8"><Aid /></div>} />
        <Route path="status" element={<div className="mx-auto max-w-5xl px-4 py-8"><Status /></div>} />
        <Route path="trust" element={<Trust />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="terms" element={<Terms />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="app" element={<AppLayout />}>
        <Route index element={<Ask />} />
        <Route path="ask" element={<Ask />} />
        <Route path="ask/:id" element={<Ask />} />
        <Route path="library" element={<Library />} />
        <Route path="documents" element={<Documents />} />
        <Route path="documents/:id" element={<DocumentDetail />} />
        <Route path="drafts" element={<Drafts />} />
        <Route path="drafts/:id" element={<DraftEditor />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="translate" element={<Translate />} />
        <Route path="aid" element={<Aid />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
