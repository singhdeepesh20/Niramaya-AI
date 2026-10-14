"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, ArrowRight, Clock3, FileImage, FileText, LoaderCircle, LogOut, RefreshCw, ShieldCheck, Sparkles, UploadCloud } from "lucide-react";
import { ApiError, authApi, documentsApi, DocumentPage, User } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";
import { clearSession, handleSessionError, readAccessToken } from "@/lib/session";

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [documents, setDocuments] = useState<DocumentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (authToken: string) => {
    setLoading(true);
    setError("");
    try {
      const [account, page] = await Promise.all([
        authApi.me(authToken), documentsApi.list(authToken, { limit: 6, sort: "newest" }),
      ]);
      setUser(account);
      setDocuments(page);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        clearSession(router);
        return;
      }
      setError(handleSessionError(cause, router));
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const saved = readAccessToken();
    if (!saved) { router.replace("/login"); return; }
    setToken(saved);
    void load(saved);
  }, [load, router]);

  function signOut() { clearSession(router); }

  return <main className="workspace-page">
    <header className="workspace-header">
      <Link className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></Link>
      <nav aria-label="Main navigation"><Link className="workspace-nav-active" href="/dashboard">Overview</Link><Link href="/documents">My documents</Link><Link href="/assistant">Health assistant</Link></nav>
      <button className="workspace-signout" onClick={signOut}><LogOut size={16} /><span>Sign out</span></button>
    </header>
    <div className="workspace-content">
      <section className="workspace-welcome">
        <div><span className="workspace-eyebrow"><ShieldCheck size={14} /> YOUR PRIVATE HEALTH SPACE</span>
          <h1>{user ? `Good to see you, ${user.username}` : "Your health records, in one place"}</h1>
          <p>Organize your medical reports and ask questions grounded in records available to your account.</p>
        </div>
        <Link className="workspace-primary" href="/documents"><UploadCloud size={17} /> Upload a report</Link>
      </section>

      {error && <div className="workspace-alert" role="alert"><span>{error}</span><button onClick={() => token && void load(token)}><RefreshCw size={15} /> Retry</button></div>}

      <section className="workspace-metrics" aria-label="Document summary">
        {[
          { label: "Total reports", value: documents?.summary.total_reports, icon: FileText, tone: "green" },
          { label: "Blood tests", value: documents?.summary.blood_tests, icon: Activity, tone: "blue" },
          { label: "Imaging reports", value: documents?.summary.imaging_reports, icon: FileImage, tone: "violet" },
          { label: "Added in last 30 days", value: documents?.summary.recent_uploads, icon: Clock3, tone: "amber" },
        ].map((item) => <article className="workspace-metric" key={item.label}><span className={`workspace-metric-icon ${item.tone}`}><item.icon size={18} /></span><span><small>{item.label}</small><strong>{loading ? "…" : item.value ?? "—"}</strong></span></article>)}
      </section>

      <div className="workspace-grid">
        <section className="workspace-panel workspace-recent">
          <div className="workspace-panel-heading"><div><h2>Recent documents</h2><p>Latest reports uploaded to your account</p></div><Link href="/documents">View all <ArrowRight size={15} /></Link></div>
          {loading && !documents ? <div className="workspace-state"><LoaderCircle className="spin" size={20} /> Loading your reports…</div>
            : documents?.items.length ? <div className="workspace-doc-list">{documents.items.map((document) => <Link href={`/documents/${document.id}`} className="workspace-doc-row" key={document.id}>
              <span className={`workspace-file-icon ${document.content_type === "application/pdf" ? "pdf" : "image"}`}>{document.content_type === "application/pdf" ? <FileText size={18} /> : <FileImage size={18} />}</span>
              <span className="workspace-doc-copy"><strong>{document.original_filename}</strong><small>{document.document_type.replaceAll("_", " ")} · {dateLabel(document.created_at)}</small></span>
              <span className={`state-badge state-${document.processing_state}`} aria-label={`Status: ${document.processing_state.replaceAll("_", " ")}`}>{document.processing_state.replaceAll("_", " ")}</span>
              <ArrowRight className="workspace-row-arrow" size={16} />
            </Link>)}</div>
            : <div className="workspace-empty"><span><FileText size={22} /></span><h3>Start with your first report</h3><p>Your library is empty. Upload a PDF or image report to begin organizing your records.</p><Link className="workspace-secondary" href="/documents"><UploadCloud size={16} /> Upload a report</Link></div>}
        </section>

        <aside className="workspace-side-column">
          <section className="assistant-promo"><span className="assistant-promo-icon"><Sparkles size={20} /></span><p className="workspace-eyebrow">GROUNDED IN YOUR RECORDS</p><h2>Ask about your health records</h2><p>Get answers using authorized report evidence, with citations to the source documents.</p><Link href="/assistant">Open assistant <ArrowRight size={15} /></Link></section>
          <section className="workspace-note"><ShieldCheck size={17} /><div><strong>Private by account</strong><p>Your records are available only through your authenticated account. AI responses are informational, not a diagnosis.</p></div></section>
        </aside>
      </div>
      <footer className="workspace-footer">{user ? `Signed in as ${user.email}` : "Secure health records workspace"}</footer>
    </div>
  </main>;
}
