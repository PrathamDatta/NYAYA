import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { Briefcase, FileSearch, FileText, Landmark, Languages, LogOut, MessageSquareText, Moon, PenLine, Scale, Settings, Sun, BookOpen, Activity } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Spinner } from "./ui";

export function Logo({ small }: { small?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand text-paper" aria-hidden><Scale className="h-5 w-5" /></span>
      <span className="leading-none"><span className="block font-display text-lg font-semibold">Nyaya Bharatha</span>{!small && <span className="block text-[11px] tracking-wide text-muted">न्याय भारत · legal information</span>}</span>
    </span>
  );
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">(() => { try { return (localStorage.getItem("theme") as "light" | "dark") || "system"; } catch { return "system"; } });
  useEffect(() => {
    const r = document.documentElement;
    if (theme === "system") r.removeAttribute("data-theme"); else r.setAttribute("data-theme", theme);
    try { if (theme === "system") localStorage.removeItem("theme"); else localStorage.setItem("theme", theme); } catch { /* storage unavailable */ }
  }, [theme]);
  const dark = theme === "dark" || (theme === "system" && typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches);
  return { dark, toggle: () => setTheme(dark ? "light" : "dark") };
}

export function ThemeToggle() {
  const { dark, toggle } = useTheme();
  return <button onClick={toggle} className="btn-ghost !px-2.5" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>{dark ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}</button>;
}

const publicNav = [{ to: "/library", label: "Library" }, { to: "/aid", label: "Legal aid" }, { to: "/trust", label: "How it works" }, { to: "/status", label: "System status" }];

export function PublicLayout() {
  const { user } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link to="/" aria-label="Nyaya Bharatha home"><Logo /></Link>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {publicNav.map((n) => <NavLink key={n.to} to={n.to} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium hover:bg-sunken ${isActive ? "text-brand" : "text-muted"}`}>{n.label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            {user ? <Link to="/app/ask" className="btn-primary">Open workspace</Link> : (<><Link to="/login" className="btn-ghost hidden sm:inline-flex">Sign in</Link><Link to="/register" className="btn-primary">Get started</Link></>)}
          </div>
        </div>
        <nav aria-label="Main (compact)" className="flex gap-1 overflow-x-auto border-t border-line px-3 py-1 md:hidden">
          {publicNav.map((n) => <NavLink key={n.to} to={n.to} className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-soft text-brand" : "text-muted"}`}>{n.label}</NavLink>)}
        </nav>
      </header>
      <main id="main" className="flex-1"><Outlet /></main>
      <Footer />
    </div>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line bg-sunken">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="space-y-3"><Logo small />
          <p className="max-w-sm text-sm text-muted">Nyaya Bharatha provides legal <em>information</em> and drafting assistance. It is not a law firm, does not give legal advice and creates no advocate–client relationship.</p>
        </div>
        <nav aria-label="Product" className="space-y-2 text-sm"><p className="font-semibold">Product</p>
          {[["/library", "Legal library"], ["/aid", "Free legal aid directory"], ["/trust", "How answers are produced"], ["/status", "System status"]].map(([to, l]) => <Link key={to} to={to} className="block text-muted hover:text-ink">{l}</Link>)}
        </nav>
        <nav aria-label="Policies" className="space-y-2 text-sm"><p className="font-semibold">Policies</p>
          {[["/privacy", "Privacy & data retention"], ["/terms", "Disclaimer & terms of use"]].map(([to, l]) => <Link key={to} to={to} className="block text-muted hover:text-ink">{l}</Link>)}
          <p className="pt-2 text-muted">In danger? Call <a className="font-semibold text-ink underline" href="tel:112">112</a>. Legal aid: <a className="font-semibold text-ink underline" href="tel:15100">15100</a>.</p>
        </nav>
      </div>
    </footer>
  );
}

const appNav = [
  { to: "/app/ask", label: "Ask", icon: MessageSquareText }, { to: "/app/library", label: "Library", icon: BookOpen },
  { to: "/app/documents", label: "Documents", icon: FileSearch }, { to: "/app/drafts", label: "Drafts", icon: PenLine },
  { to: "/app/cases", label: "Cases", icon: Briefcase }, { to: "/app/translate", label: "Translate", icon: Languages },
  { to: "/app/aid", label: "Legal aid", icon: Landmark }, { to: "/app/settings", label: "Settings", icon: Settings },
];

export function AppLayout() {
  const { user, loading, logout } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="grid min-h-screen place-items-center"><Spinner label="Loading…" /></div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <aside className="hidden border-r border-line bg-surface md:flex md:flex-col">
        <div className="p-4"><Link to="/" aria-label="Home"><Logo small /></Link></div>
        <nav aria-label="Workspace" className="flex-1 space-y-0.5 px-2">
          {appNav.map(({ to, label, icon: I }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${isActive ? "bg-brand-soft text-brand-strong" : "text-muted hover:bg-sunken hover:text-ink"}`}><I className="h-4 w-4" aria-hidden />{label}</NavLink>
          ))}
          <NavLink to="/status" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted hover:bg-sunken"><Activity className="h-4 w-4" aria-hidden />System status</NavLink>
        </nav>
        <div className="space-y-2 border-t border-line p-3 text-sm">
          <p className="truncate text-muted" title={user.email}>{user.display_name || user.email}</p>
          <div className="flex items-center gap-1"><ThemeToggle /><button onClick={() => void logout()} className="btn-ghost flex-1"><LogOut className="h-4 w-4" aria-hidden />Sign out</button></div>
        </div>
      </aside>
      <div className="min-w-0">
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-paper/95 px-3 py-2 backdrop-blur md:hidden">
          <Link to="/" aria-label="Home"><Logo small /></Link>
          <div className="flex items-center"><ThemeToggle /><button onClick={() => void logout()} className="btn-ghost !px-2.5" aria-label="Sign out"><LogOut className="h-4 w-4" aria-hidden /></button></div>
        </div>
        <nav aria-label="Workspace (compact)" className="sticky top-[53px] z-20 flex gap-1 overflow-x-auto border-b border-line bg-paper px-2 py-1.5 md:hidden">
          {appNav.map(({ to, label, icon: I }) => <NavLink key={to} to={to} className={({ isActive }) => `flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-soft text-brand-strong" : "text-muted"}`}><I className="h-4 w-4" aria-hidden />{label}</NavLink>)}
        </nav>
        <main id="main" className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8 md:py-8"><Outlet /></main>
      </div>
    </div>
  );
}

export { FileText };
