"use client";

import Link from "next/link";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, FileImage, FileText, LoaderCircle, LogOut, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { ApiError, documentsApi, MedicalDocument, processingStateLabels, ProcessingStatus, ExtractedEntities, ExtractedPages, ExtractedTables, ProcessingHistory } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";
import { clearSession, handleSessionError, readAccessToken } from "@/lib/session";

const ACTIVE_STATES = new Set(["uploaded", "queued", "processing", "deletion_pending"]);

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const router = useRouter();
  const [token, setToken] = useState("");
  const [document, setDocument] = useState<MedicalDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [processing, setProcessing] = useState<ProcessingStatus | null>(null);
  const [extractions, setExtractions] = useState<ExtractedEntities | null>(null);
  const [pages, setPages] = useState<ExtractedPages | null>(null);
  const [tables, setTables] = useState<ExtractedTables | null>(null);
  const [history, setHistory] = useState<ProcessingHistory | null>(null);
  const state = document?.processing_state;

  const load = useCallback(async (authToken: string, quiet = false) => {
    if (!quiet) setLoading(true); else setRefreshing(true);
    try {
      const result = await documentsApi.get(authToken, documentId);
      setDocument(result); setError("");
      const [statusResult, entityResult, pageResult, tableResult, historyResult] = await Promise.all([
        documentsApi.status(authToken, documentId), documentsApi.extractions(authToken, documentId),
        documentsApi.pages(authToken, documentId), documentsApi.tables(authToken, documentId),
        documentsApi.history(authToken, documentId),
      ]);
      setProcessing(statusResult); setExtractions(entityResult); setPages(pageResult); setTables(tableResult); setHistory(historyResult);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      if (cause instanceof ApiError && cause.status === 404 && document?.processing_state === "deletion_pending") {
        setDocument(null); setNotice("This report is no longer available. The backend confirmed its removal."); return;
      }
      setError(handleSessionError(cause, router));
    } finally { setLoading(false); setRefreshing(false); }
  }, [document?.processing_state, documentId, router]);

  useEffect(() => {
    const saved = readAccessToken();
    if (!saved) { router.replace("/login"); return; }
    setToken(saved); void load(saved);
  }, [load, router]);

  useEffect(() => {
    if (!token || !state || !ACTIVE_STATES.has(state)) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = state === "deletion_pending" ? 10_000 : 5_000;
    const poll = async () => {
      try {
        const result = await documentsApi.get(token, documentId);
        if (!alive) return;
        setDocument(result); setError(""); delay = result.processing_state === "deletion_pending" ? 10_000 : 5_000;
        if (!ACTIVE_STATES.has(result.processing_state)) {
          const [statusResult, entityResult, pageResult, tableResult, historyResult] = await Promise.all([
            documentsApi.status(token, documentId), documentsApi.extractions(token, documentId),
            documentsApi.pages(token, documentId), documentsApi.tables(token, documentId),
            documentsApi.history(token, documentId),
          ]);
          if (alive) { setProcessing(statusResult); setExtractions(entityResult); setPages(pageResult); setTables(tableResult); setHistory(historyResult); }
        }
      } catch (cause) {
        if (!alive) return;
        if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
        if (cause instanceof ApiError && cause.status === 404) { setDocument(null); setNotice("This report is no longer available to your account."); return; }
        setError(handleSessionError(cause, router)); delay = Math.min(delay * 2, 30_000);
      }
      if (alive) timer = setTimeout(poll, delay);
    };
    timer = setTimeout(poll, delay);
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [documentId, router, state, token]);

  async function openPreview() {
    if (!token || !document) return;
    setBusy(true); setError("");
    try { setPreviewUrl((await documentsApi.viewUrl(token, document.id)).url); }
    catch (cause) { setError(handleSessionError(cause, router)); }
    finally { setBusy(false); }
  }

  async function reprocess() {
    if (!token || !document || busy) return;
    setBusy(true); setError(""); setNotice("");
    try { setDocument(await documentsApi.reprocess(token, document.id)); setNotice("Reprocessing was queued by the backend."); }
    catch (cause) { setError(handleSessionError(cause, router)); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!token || !document || busy || !window.confirm(`Delete “${document.original_filename}”?`)) return;
    setBusy(true); setError("");
    try { await documentsApi.remove(token, document.id); setDocument(null); setNotice("The backend confirmed deletion."); setPreviewUrl(""); }
    catch (cause) { setError(handleSessionError(cause, router)); await load(token, true); }
    finally { setBusy(false); }
  }

  return <main className="workspace-page">
    <header className="workspace-header"><Link className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></Link><nav aria-label="Main navigation"><Link href="/dashboard">Overview</Link><Link className="workspace-nav-active" href="/documents">My documents</Link><Link href="/assistant">Health assistant</Link></nav><button className="workspace-signout" onClick={() => clearSession(router)}><LogOut size={16} /><span>Sign out</span></button></header>
    <div className="workspace-content"><Link className="workspace-back" href="/documents"><ArrowLeft size={15} /> Back to documents</Link>
      {loading ? <div className="workspace-panel workspace-state"><LoaderCircle className="spin" size={20} /> Loading report details…</div> : document ? <>
        <section className="detail-heading"><span className={`workspace-file-icon large ${document.content_type === "application/pdf" ? "pdf" : "image"}`}>{document.content_type === "application/pdf" ? <FileText size={23} /> : <FileImage size={23} />}</span><div className="detail-title"><span className="workspace-eyebrow"><ShieldCheck size={14} /> PRIVATE DOCUMENT</span><h1>{document.original_filename}</h1><p>{document.document_type.replace(/_/g, " ")} · Uploaded {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(document.created_at))}</p></div><span className={`state-badge state-${state}`}>{state ? processingStateLabels[state] : "Status unavailable"}</span></section>
        {error && <div className="workspace-alert" role="alert"><span>{error}</span><button onClick={() => void load(token, true)}><RefreshCw size={15} /> Retry</button></div>}{notice && <div className="workspace-success" role="status">{notice}</div>}
        <div className="detail-grid"><section className="workspace-panel detail-main">
          <div className="workspace-panel-heading"><div><h2>Processing status</h2><p>Current state reported by the document service</p></div><button className="workspace-icon-button" onClick={() => void load(token, true)} disabled={refreshing} aria-label="Refresh report status"><RefreshCw size={16} className={refreshing ? "spin" : ""} /></button></div>
          <div className={`detail-status detail-${state}`}><span className="detail-status-dot" /><div><strong>{state ? processingStateLabels[state] : "Status unavailable"}</strong><p>{state === "queued" || state === "uploaded" ? "The upload is confirmed. Processing has not completed yet." : state === "processing" ? "A worker is processing this report. Status refreshes automatically while work is active." : state === "review_required" ? "The backend indicates that review is needed. See the available review contract below." : state === "failed" ? "The backend reports a processing failure. You can request reprocessing if available." : state === "completed" ? "The backend reports that configured mandatory processing stages succeeded." : state === "deletion_pending" ? "Deletion has been requested and is still being reconciled." : "The current processing state could not be determined."}</p></div></div>
          <div className="detail-actions"><button className="workspace-primary" onClick={() => void openPreview()} disabled={busy || document.upload_status !== "ready"}><ExternalLink size={16} /> Open secure preview</button>{(state === "failed" || state === "completed" || state === "review_required") && <button className="workspace-secondary" onClick={() => void reprocess()} disabled={busy}><RefreshCw size={15} /> Reprocess</button>}<button className="workspace-danger" onClick={() => void remove()} disabled={busy || state === "deletion_pending"}><Trash2 size={15} /> Delete report</button></div>
          <section className="document-results"><div className="workspace-panel-heading"><div><h2>Extracted information</h2><p>Rule-based extraction from this report · generation {processing?.processing_generation ?? extractions?.generation ?? 0}</p></div></div>
            {processing?.processing && <div className="processing-summary"><strong>Classification:</strong> {String((processing.processing.classification as Record<string, unknown> | undefined)?.type ?? document.document_type)}{typeof (processing.processing.classification as Record<string, unknown> | undefined)?.rule_id === "string" && <span> · rule {String((processing.processing.classification as Record<string, unknown>).rule_id)}</span>}{Array.isArray(processing.processing.review_reasons) && (processing.processing.review_reasons as string[]).length > 0 && <p>Review notes: {(processing.processing.review_reasons as string[]).join(", ")}</p>}</div>}
            {state === "queued" || state === "processing" || state === "uploaded" ? <p className="result-empty">Extraction results will appear here after the worker processes the report.</p> : extractions?.items.length ? <div className="result-table-wrap"><table className="result-table"><thead><tr><th>Finding</th><th>Value</th><th>Normalized</th><th>Reference range</th><th>Source</th></tr></thead><tbody>{extractions.items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.category.replace(/_/g, " ")}</small></td><td>{item.value ?? item.qualitative_value ?? "—"}{item.reported_abnormal === true && <em className="result-flag">Flagged</em>}</td><td>{item.normalized_value ? `${item.normalized_value} ${item.normalized_unit ?? ""}` : "—"}</td><td>{item.reference_range ?? "—"}</td><td>{item.page_number ? `Page ${item.page_number}` : "—"}<small>{item.extraction_method}</small></td></tr>)}</tbody></table></div> : <p className="result-empty">No supported findings were extracted. This may mean the report format is not recognized or text extraction needs review.</p>}
          </section>
          <section className="document-results"><h2>Extracted tables</h2>{tables?.items.length ? tables.items.map((table) => <div className="result-table-wrap" key={`${table.page_number}-${table.table_index}`}><p className="result-caption">Page {table.page_number} · table {table.table_index + 1}</p><table className="result-table"><thead><tr>{table.headers.map((header, i) => <th key={i}>{header || `Column ${i + 1}`}</th>)}</tr></thead><tbody>{table.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>) : <p className="result-empty">No tables were detected in the current extraction.</p>}</section>
          <section className="document-results"><h2>Page text</h2>{pages?.items.length ? pages.items.map((page) => <details className="page-excerpt" key={page.page_number}><summary>Page {page.page_number} · {page.character_count} characters · {page.extraction_method}{page.ocr_required ? ` · OCR ${page.ocr_status}` : ""}</summary><pre>{page.extracted_text || "No text could be extracted from this page."}</pre>{page.warnings.map((warning) => <small key={warning} className="result-warning">{warning}</small>)}</details>) : <p className="result-empty">Page text is not available until processing completes.</p>}</section>
          <section className="document-results"><h2>Processing history</h2>{history?.events.length ? <ol className="processing-timeline">{history.events.map((event) => <li key={event.state_version}><strong>{processingStateLabels[event.next_state as keyof typeof processingStateLabels] ?? event.next_state.replace(/_/g, " ")}</strong><span>{event.reason_code.replace(/_/g, " ")} · {new Date(event.created_at).toLocaleString()}</span></li>)}</ol> : <p className="result-empty">No processing events are available yet.</p>}{processing?.stages.length ? <div className="stage-list">{processing.stages.map((stage) => <div key={stage.stage}><span>{stage.stage.replace(/_/g, " ")}</span><strong>{stage.status.replace(/_/g, " ")}</strong>{stage.reason_code && <small>{stage.reason_code.replace(/_/g, " ")}</small>}</div>)}</div> : null}</section>
        </section><aside className="workspace-panel detail-side"><h2>Report details</h2><dl><div><dt>File name</dt><dd>{document.original_filename}</dd></div><div><dt>File type</dt><dd>{document.content_type}</dd></div><div><dt>Size</dt><dd>{(document.file_size / (1024 * 1024)).toFixed(2)} MB</dd></div><div><dt>Uploaded</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(document.created_at))}</dd></div><div><dt>Updated</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(document.updated_at))}</dd></div></dl>{state === "review_required" && <div className="review-callout"><h3>Review requested</h3><p>The API supplies no review fields or extracted source text, but supports a guarded completion action.</p><Link href={`/documents/${document.id}/review`}>View review options <span aria-hidden="true">→</span></Link></div>}</aside></div>
      </> : <section className="workspace-panel workspace-empty detail-not-found"><span><FileText size={23} /></span><h1>Report unavailable</h1><p>{notice || error || "We couldn't load this document. It may have been removed or may not be available to your account."}</p><Link className="workspace-secondary" href="/documents">Return to documents</Link></section>}
      <footer className="workspace-footer"><ShieldCheck size={14} /> Medical information is shown as provided by your records; this is not a diagnosis.</footer>
    </div>
    {previewUrl && document && <div className="secure-view-backdrop" role="presentation" onClick={() => setPreviewUrl("")}><section className="secure-view-dialog" role="dialog" aria-modal="true" aria-label={`Secure preview: ${document.original_filename}`} onClick={(event) => event.stopPropagation()}><header><div><strong>{document.original_filename}</strong><small>Short-lived private viewing link</small></div><button onClick={() => setPreviewUrl("")} aria-label="Close preview">Close</button></header>{document.content_type === "application/pdf" ? <iframe title={`Preview of ${document.original_filename}`} src={previewUrl} referrerPolicy="no-referrer" /> : <Image unoptimized width={1600} height={1200} src={previewUrl} alt={document.original_filename} referrerPolicy="no-referrer" />}</section></div>}
  </main>;
}
