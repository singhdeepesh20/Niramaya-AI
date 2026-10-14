"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Activity, ArrowDownToLine, ArrowLeft, CalendarDays, Check, ChevronDown, Clock3, ExternalLink, FileImage, FileText, FolderOpen, LoaderCircle, LogOut, Search, ShieldCheck, Trash2, UploadCloud, X } from "lucide-react";
import { ApiError, DocumentPage, documentsApi, MedicalDocument, processingStateLabels } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";

const TYPES = ["cbc", "blood_test", "mri", "prescription", "discharge_summary", "x_ray", "other"];
const LABELS: Record<string, string> = { cbc: "CBC", blood_test: "Blood test", mri: "MRI", prescription: "Prescription", discharge_summary: "Discharge summary", x_ray: "X-ray", other: "Other" };
const MAX_FILE_SIZE = 15 * 1024 * 1024;

function bytes(value: number) { return value < 1024 * 1024 ? `${Math.max(1, Math.round(value / 1024))} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`; }
function readableDate(value: string) { return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(value)); }

export default function ReportsPage() {
  const router = useRouter();
  const picker = useRef<HTMLInputElement>(null);
  const [token, setToken] = useState("");
  const [data, setData] = useState<DocumentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedType, setSelectedType] = useState("other");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState("");
  const [preview, setPreview] = useState<{ document: MedicalDocument; url: string } | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<MedicalDocument | null>(null);

  const load = useCallback(async (authToken: string, currentOffset = 0) => {
    setLoading(true); setError("");
    try { setData(await documentsApi.list(authToken, { q: search.trim(), document_type: type, date_from: dateFrom, date_to: dateTo, sort, limit: 12, offset: currentOffset })); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { sessionStorage.removeItem("niramaya_access_token"); router.replace("/login"); return; }
      setError(cause instanceof ApiError ? cause.message : "Your reports could not be loaded. Please try again.");
    } finally { setLoading(false); }
  }, [dateFrom, dateTo, router, search, sort, type]);

  useEffect(() => {
    const saved = sessionStorage.getItem("niramaya_access_token");
    if (!saved) { router.replace("/login"); return; }
    setToken(saved);
  }, [router]);

  useEffect(() => { if (token) { setOffset(0); void load(token, 0); } }, [search, type, sort, token, load]);
  function signOut() { sessionStorage.removeItem("niramaya_access_token"); router.replace("/login"); }

  async function handleFiles(files: FileList | File[]) {
    const file = files[0]; if (!file || !token) return;
    setNotice(""); setError("");
    if (!/\.(pdf|jpe?g|png)$/i.test(file.name)) { setError("Choose a PDF, JPEG, or PNG report."); return; }
    if (file.size === 0 || file.size > MAX_FILE_SIZE) { setError("Choose a non-empty report up to 15 MB."); return; }
    setSelectedFile(file);
  }
  async function startUpload() {
    if (!selectedFile || !token) return;
    setUploading(true); setProgress(0);
    try {
      const result = await documentsApi.upload(token, selectedFile, selectedType, setProgress);
      setUploadedDocument(result); setNotice(""); setSelectedFile(null); await load(token, 0);
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : "The report could not be uploaded. Please try again."); }
    finally { setUploading(false); setProgress(0); if (picker.current) picker.current.value = ""; }
  }
  function inputChanged(event: ChangeEvent<HTMLInputElement>) { if (event.target.files) void handleFiles(event.target.files); }
  function dragOver(event: DragEvent<HTMLElement>) { event.preventDefault(); setDragging(true); }
  function drop(event: DragEvent<HTMLElement>) { event.preventDefault(); setDragging(false); void handleFiles(event.dataTransfer.files); }

  async function openPreview(document: MedicalDocument) {
    if (!token) return; setBusyId(document.id); setError("");
    try { const result = await documentsApi.viewUrl(token, document.id); setPreview({ document, url: result.url }); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "This report could not be opened."); }
    finally { setBusyId(""); }
  }
  async function download(document: MedicalDocument) {
    if (!token) return; setBusyId(document.id); setError("");
    try { const result = await documentsApi.downloadUrl(token, document.id); window.location.assign(result.url); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "This report could not be downloaded."); }
    finally { setBusyId(""); }
  }
  async function remove(document: MedicalDocument) {
    if (!token || !window.confirm(`Delete “${document.original_filename}”?`)) return;
    setBusyId(document.id); setError("");
    try { await documentsApi.remove(token, document.id); setNotice("Report deleted."); await load(token); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "This report could not be deleted. Please try again."); }
    finally { setBusyId(""); }
  }

  return <main className="reports-page">
    <header className="reports-header">
      <a className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></a>
      <nav aria-label="Main navigation"><a className="report-nav-active" href="/reports">My reports</a><a href="/dashboard">Overview</a></nav>
      <button className="signout-button" onClick={signOut}><LogOut size={16} /> Sign out</button>
    </header>
    <div className="reports-content">
      <a className="reports-back" href="/dashboard"><ArrowLeft size={15} /> Back to overview</a>
      <div className="reports-title-row"><div><span className="reports-eyebrow"><ShieldCheck size={14} /> PRIVATE HEALTH SPACE</span><h1>Medical reports</h1><p>Your records, securely stored and easy to find.</p></div><button className="reports-upload-button" onClick={() => picker.current?.click()} disabled={uploading}><UploadCloud size={17} /> Upload report</button></div>

      <section className="reports-stats" aria-label="Report summary">
        {[{ title: "All reports", value: data?.summary.total_reports ?? "—", icon: FolderOpen, tone: "green" }, { title: "Blood tests", value: data?.summary.blood_tests ?? "—", icon: Activity, tone: "blue" }, { title: "Imaging", value: data?.summary.imaging_reports ?? "—", icon: FileImage, tone: "violet" }, { title: "Added this month", value: data?.summary.recent_uploads ?? "—", icon: Clock3, tone: "amber" }].map((stat) => <article className="reports-stat" key={stat.title}><span className={`reports-stat-icon ${stat.tone}`}><stat.icon size={18} /></span><span><small>{stat.title}</small><strong>{loading && data === null ? "…" : stat.value}</strong></span></article>)}
      </section>

      <section className={`upload-dropzone ${dragging ? "is-dragging" : ""} ${uploading ? "is-uploading" : ""}`} onDragOver={dragOver} onDragLeave={() => setDragging(false)} onDrop={drop} aria-label="Upload a report">
        <input ref={picker} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={inputChanged} hidden />
        <span className="upload-drop-icon">{uploading ? <LoaderCircle size={21} className="spin" /> : <UploadCloud size={21} />}</span>
        <div className="upload-drop-copy"><strong>{uploading ? "Uploading securely…" : "Drop a report here, or browse"}</strong><small>{uploading ? "Your report is sent over an encrypted connection." : "PDF, JPEG or PNG · Up to 15 MB · Private to your account"}</small>{uploading && <div className="upload-progress"><span style={{ width: `${progress}%` }} /></div>}</div>
        {!uploading && <button type="button" className="browse-button" onClick={() => picker.current?.click()}>Browse files</button>}
      </section>
      {selectedFile && <div className="selected-report"><span className="selected-file-icon"><FileText size={18} /></span><div><strong>{selectedFile.name}</strong><small>{bytes(selectedFile.size)} · Ready to upload</small></div><label className="selected-category"><span className="sr-only">Report category</span><select disabled={uploading} value={selectedType} onChange={(event) => setSelectedType(event.target.value)}>{TYPES.map((entry) => <option key={entry} value={entry}>{LABELS[entry]}</option>)}</select><ChevronDown size={13} /></label><button className="selected-cancel" disabled={uploading} onClick={() => { setSelectedFile(null); setError(""); }}>Remove</button><button className="reports-upload-button" disabled={uploading} onClick={() => void startUpload()}>{uploading ? <><LoaderCircle size={15} className="spin" /> Uploading {progress}%</> : <><UploadCloud size={15} /> Upload now</>}</button></div>}
      {error && <div className="reports-alert" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button></div>}
      {uploadedDocument && <div className="reports-success" role="status"><Check size={16} /> <span>{uploadedDocument.original_filename} uploaded; {processingStateLabels[uploadedDocument.processing_state]}.</span><Link href={`/documents/${uploadedDocument.id}`}>View status</Link><button onClick={() => setUploadedDocument(null)} aria-label="Dismiss message"><X size={15} /></button></div>}
      {notice && <div className="reports-success" role="status"><Check size={16} /> {notice}<button onClick={() => setNotice("")} aria-label="Dismiss message"><X size={15} /></button></div>}

      <section className="reports-library">
        <div className="library-heading"><div><h2>Your library</h2><p>{data ? `${data.total} ${data.total === 1 ? "report" : "reports"}` : "Your uploaded reports"}</p></div><button className="library-refresh" onClick={() => token && void load(token)} aria-label="Refresh reports"><LoaderCircle size={16} className={loading ? "spin" : ""} /></button></div>
        <div className="report-filters"><label className="report-search"><Search size={16} /><input aria-label="Search reports" placeholder="Search by report name…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><label className="report-select"><span className="sr-only">Filter by type</span><select value={type} onChange={(event) => setType(event.target.value)}><option value="">All types</option>{TYPES.map((entry) => <option key={entry} value={entry}>{LABELS[entry]}</option>)}</select><ChevronDown size={14} /></label><label className="report-date"><CalendarDays size={14} /><span className="sr-only">Uploaded from</span><input aria-label="Uploaded from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label className="report-date"><CalendarDays size={14} /><span className="sr-only">Uploaded through</span><input aria-label="Uploaded through" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label><label className="report-select"><span className="sr-only">Sort reports</span><select value={sort} onChange={(event) => setSort(event.target.value as "newest" | "oldest")}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select><ChevronDown size={14} /></label></div>
        {loading && !data ? <div className="reports-state"><LoaderCircle size={22} className="spin" /><span>Loading your reports…</span></div> : data?.items.length ? <div className="report-list">{data.items.map((document) => <article className={`report-card ${document.upload_status === "deleting" ? "report-pending" : ""}`} key={document.id}><span className={`report-file-icon ${document.content_type === "application/pdf" ? "pdf" : "image"}`}>{document.content_type === "application/pdf" ? <FileText size={21} /> : <FileImage size={21} />}</span><div className="report-info"><strong title={document.original_filename}>{document.original_filename}</strong><span>{LABELS[document.document_type] || "Medical report"}<i />{bytes(document.file_size)}<i /><CalendarDays size={13} /> {readableDate(document.created_at)}</span></div><span className={`report-status ${document.processing_state}`} aria-label={`Processing status: ${processingStateLabels[document.processing_state]}`}>{processingStateLabels[document.processing_state]}</span><div className="report-actions"><Link className="report-open-link" href={`/documents/${document.id}`} title="Open report details" aria-label={`Details for ${document.original_filename}`}><FileText size={16} /></Link><button title="Preview report" aria-label={`Preview ${document.original_filename}`} onClick={() => void openPreview(document)} disabled={!!busyId || document.upload_status !== "ready"}><ExternalLink size={16} /></button><button title="Download" aria-label={`Download ${document.original_filename}`} onClick={() => void download(document)} disabled={!!busyId || document.upload_status !== "ready"}><ArrowDownToLine size={16} /></button><button title="Delete" aria-label={`Delete ${document.original_filename}`} onClick={() => void remove(document)} disabled={!!busyId}><Trash2 size={16} /></button></div>{busyId === document.id && <span className="report-busy"><LoaderCircle size={14} className="spin" /></span>}</article>)}</div> : <div className="reports-empty"><span><FolderOpen size={23} /></span><h3>{search || type || dateFrom || dateTo ? "No matching reports" : "Your reports will appear here"}</h3><p>{search || type || dateFrom || dateTo ? "Try a different search or filter." : "Upload a lab result, prescription, or imaging report to get started."}</p>{!search && !type && !dateFrom && !dateTo && <button className="reports-upload-button" onClick={() => picker.current?.click()}><UploadCloud size={16} /> Upload your first report</button>}</div>}
        {data && data.total > 12 && <div className="reports-pagination"><span>Showing {offset + 1}–{Math.min(offset + data.items.length, data.total)} of {data.total}</span><div><button disabled={offset === 0 || loading} onClick={() => { const next = Math.max(offset - 12, 0); setOffset(next); if (token) void load(token, next); }}>Previous</button><button disabled={offset + 12 >= data.total || loading} onClick={() => { const next = offset + 12; setOffset(next); if (token) void load(token, next); }}>Next</button></div></div>}
      </section>
      <footer className="reports-footer"><ShieldCheck size={15} /> Your reports are private and accessible only to your account.</footer>
    </div>
    {preview && <div className="preview-backdrop" role="presentation" onClick={() => setPreview(null)}><section className="preview-dialog" role="dialog" aria-modal="true" aria-label={preview.document.original_filename} onClick={(event) => event.stopPropagation()}><header><div><strong>{preview.document.original_filename}</strong><small>Secure preview · Link expires shortly</small></div><button onClick={() => setPreview(null)} aria-label="Close preview"><X size={19} /></button></header><div className="preview-content">{preview.document.content_type === "application/pdf" ? <iframe title={preview.document.original_filename} src={preview.url} /> : <Image unoptimized width={1600} height={1200} src={preview.url} alt={preview.document.original_filename} />}</div><footer><span><ShieldCheck size={14} /> Private report</span><button onClick={() => void download(preview.document)}><ArrowDownToLine size={15} /> Download</button></footer></section></div>}
  </main>;
}
