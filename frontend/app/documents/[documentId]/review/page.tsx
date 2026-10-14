"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Check, FileText, LoaderCircle, LogOut, ShieldCheck } from "lucide-react";
import { ApiError, documentsApi, MedicalDocument } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";
import { clearSession, handleSessionError, readAccessToken } from "@/lib/session";

export default function DocumentReviewPage() {
  const params = useParams<{ documentId: string }>();
  const documentId = params.documentId;
  const router = useRouter();
  const [token, setToken] = useState("");
  const [document, setDocument] = useState<MedicalDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const saved = readAccessToken();
    if (!saved) { router.replace("/login"); return; }
    setToken(saved);
    documentsApi.get(saved, documentId).then(setDocument).catch((cause: unknown) => {
      if (cause instanceof ApiError && cause.status === 401) clearSession(router);
      else setError(handleSessionError(cause, router));
    }).finally(() => setLoading(false));
  }, [documentId, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !document || !confirmed || submitting) return;
    setSubmitting(true); setError(""); setNotice("");
    try {
      const updated = await documentsApi.completeReview(token, document.id);
      setDocument(updated); setNotice("The backend accepted the review and confirmed the new document state.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setError(handleSessionError(cause, router));
    } finally { setSubmitting(false); }
  }

  return <main className="workspace-page">
    <header className="workspace-header"><Link className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></Link><nav aria-label="Main navigation"><Link href="/dashboard">Overview</Link><Link className="workspace-nav-active" href="/documents">My documents</Link><Link href="/assistant">Health assistant</Link></nav><button className="workspace-signout" onClick={() => clearSession(router)}><LogOut size={16} /><span>Sign out</span></button></header>
    <div className="workspace-content review-content"><Link className="workspace-back" href={`/documents/${documentId}`}><ArrowLeft size={15} /> Back to report</Link>
      {loading ? <div className="workspace-panel workspace-state"><LoaderCircle size={20} className="spin" /> Loading review status…</div>
        : document ? <section className="workspace-panel review-panel"><span className="review-icon"><ShieldCheck size={22} /></span><span className="workspace-eyebrow">HUMAN REVIEW</span><h1>Review report status</h1><p className="review-document"><FileText size={16} /> {document.original_filename}</p>
          <div className="review-status-line"><strong>Backend status</strong><span className={`state-badge state-${document.processing_state}`}>{document.processing_state.replaceAll("_", " ")}</span></div>
          <div className="review-gap"><h2>Review details aren’t available yet</h2><p>The current API does not return extracted fields, source text, confidence scores, or individual accept/reject operations. This screen will not invent or edit clinical data.</p><p>The backend offers a guarded review-completion operation. It accepts the review only after its required processing and validation stages have succeeded.</p></div>
          {error && <div className="workspace-alert" role="alert">{error}</div>}{notice && <div className="workspace-success" role="status"><Check size={16} /> {notice}</div>}
          {document.processing_state === "review_required" && <form onSubmit={(event) => void submit(event)} className="review-form"><label className="review-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>I have reviewed the information available to me and want the backend to validate whether this report can be completed.</span></label><button className="workspace-primary" type="submit" disabled={!confirmed || submitting}>{submitting ? <><LoaderCircle size={15} className="spin" /> Submitting review…</> : "Submit review confirmation"}</button></form>}
          {document.processing_state !== "review_required" && <p className="review-unavailable">This document is not currently in the `review_required` state, so no review action is available.</p>}
          <p className="review-status-note">The screen updates only from the response returned by the backend. A rejected request does not change the document state.</p>
        </section> : <section className="workspace-panel workspace-empty"><span><FileText size={22} /></span><h1>Report unavailable</h1><p>{error || "This report is no longer available to your account."}<br />{documentId && <Link href="/documents">Return to your documents</Link>}</p></section>}
    </div>
  </main>;
}
