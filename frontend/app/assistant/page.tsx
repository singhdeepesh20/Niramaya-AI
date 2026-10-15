"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, Check, FileText, LoaderCircle, LogOut, MessageCircle, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { ApiError, ChatHistoryItem, HealthAnswer, IndexingStatus, MedicalDocument, documentsApi, healthApi } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";
import { SourceList } from "@/components/assistant/source-list";
import { clearSession, handleSessionError, readAccessToken } from "@/lib/session";

type ChatEntry = {
  id: string;
  question: string;
  answer: string;
  citations: HealthAnswer["citations"];
  evidence: HealthAnswer["evidence"];
  generation_status: HealthAnswer["generation_status"] | "unknown";
};
type SearchableDocument = MedicalDocument & { indexing: IndexingStatus | null };

function suggestedQuestions(documents: SearchableDocument[]): string[] {
  const searchable = documents.filter(isSearchable);
  const questions: string[] = [];
  const labReports = searchable.filter((document) => document.document_type === "cbc" || document.document_type === "blood_test");
  const imagingReports = searchable.filter((document) => document.document_type === "mri" || document.document_type === "x_ray");
  if (labReports.length) {
    questions.push("What hemoglobin value is recorded in my latest CBC report?");
    questions.push("Summarize the laboratory results in my uploaded report.");
    questions.push("Find the TSH result in my uploaded reports.");
  }
  if (imagingReports.some((document) => document.document_type === "mri")) questions.push("What does my MRI report say in its impression section?");
  if (labReports.length > 1) questions.push("Compare the dates of my available blood test reports.");
  return questions;
}

function historyEntry(item: ChatHistoryItem): ChatEntry {
  const validStatus = item.generation_status === "generated" || item.generation_status === "evidence_only" || item.generation_status === "insufficient_evidence";
  return {
    id: item.id,
    question: item.question,
    answer: item.answer,
    citations: Array.isArray(item.citations) ? item.citations : [],
    evidence: [],
    generation_status: validStatus ? item.generation_status as ChatEntry["generation_status"] : "unknown",
  };
}

function responseLabel(status: ChatEntry["generation_status"]): string {
  if (status === "evidence_only") return "Evidence retrieved · answer generation unavailable";
  if (status === "insufficient_evidence") return "Not enough evidence in available records";
  if (status === "generated") return "Answer based on retrieved records";
  return "Assistant response";
}

function indexDescription(document: SearchableDocument): string {
  if (document.processing_state !== "completed") return `Document ${document.processing_state.replaceAll("_", " ")}`;
  if (!document.indexing) return "Index status unavailable";
  if (document.indexing.status === "completed" && document.indexing.chunk_count > 0) return `${document.indexing.chunk_count} searchable excerpts`;
  if (document.indexing.status === "queued" || document.indexing.status === "indexing") return "Indexing in progress";
  if (document.indexing.status === "failed") return "Indexing failed";
  return "Not yet searchable";
}

function isSearchable(document: SearchableDocument): boolean {
  return document.processing_state === "completed" && document.indexing?.status === "completed" && document.indexing.chunk_count > 0;
}

export default function AssistantPage() {
  const router = useRouter();
  const input = useRef<HTMLTextAreaElement>(null);
  const [token, setToken] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [documents, setDocuments] = useState<SearchableDocument[]>([]);
  const [documentTotal, setDocumentTotal] = useState(0);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [documentError, setDocumentError] = useState("");

  async function loadHistory(authToken: string, showLoader = false) {
    if (showLoader) setLoading(true);
    setError("");
    try {
      setEntries((await healthApi.history(authToken)).map(historyEntry));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setError(handleSessionError(cause, router));
    } finally { setLoading(false); }
  }

  async function loadDocuments(authToken: string) {
    setDocumentsLoading(true);
    setDocumentError("");
    try {
      const page = await documentsApi.list(authToken, { limit: 50, offset: 0, sort: "newest" });
      setDocumentTotal(page.total);
      const statuses = await Promise.all(page.items.map(async (document) => {
        if (document.processing_state !== "completed") return [document.id, null] as const;
        try { return [document.id, await documentsApi.indexingStatus(authToken, document.id)] as const; }
        catch (cause) {
          if (cause instanceof ApiError && cause.status === 401) throw cause;
          return [document.id, null] as const;
        }
      }));
      const statusById = new Map(statuses);
      setDocuments(page.items.map((document) => ({ ...document, indexing: statusById.get(document.id) ?? null })));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setDocuments([]);
      setDocumentTotal(0);
      setDocumentError(handleSessionError(cause, router));
    } finally { setDocumentsLoading(false); }
  }

  useEffect(() => {
    const saved = readAccessToken();
    if (!saved) { router.replace("/login"); return; }
    setToken(saved);
    void loadHistory(saved, true);
    void loadDocuments(saved);
    // The tab-scoped session is read once when the protected page mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!token || !cleanQuestion || cleanQuestion.length > 1000 || sending) return;
    setSending(true);
    setError("");
    try {
      const result = await healthApi.ask(token, cleanQuestion, selectedDocumentIds.length ? selectedDocumentIds : undefined);
      const entry: ChatEntry = {
        id: `reply-${crypto.randomUUID()}`,
        question: cleanQuestion,
        answer: result.answer,
        citations: result.citations,
        evidence: result.evidence,
        generation_status: result.generation_status,
      };
      setEntries((current) => [entry, ...current]);
      setQuestion("");
      input.current?.focus();
      // The backend persists each question and answer; refresh from that source for its ID and timestamp.
      try { setEntries((await healthApi.history(token)).map(historyEntry)); }
      catch (cause) {
        if (cause instanceof ApiError && cause.status === 401) clearSession(router);
        // Keep the successful response visible if history refresh is temporarily unavailable.
      }
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setError(handleSessionError(cause, router));
    } finally { setSending(false); }
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) => current.includes(documentId)
      ? current.filter((id) => id !== documentId)
      : [...current, documentId]);
  }

  return <main className="workspace-page assistant-page">
    <header className="workspace-header"><Link className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></Link><nav aria-label="Main navigation"><Link href="/dashboard">Overview</Link><Link href="/documents">My documents</Link><Link className="workspace-nav-active" href="/assistant" aria-current="page">Health assistant</Link></nav><button className="workspace-signout" onClick={() => clearSession(router)}><LogOut size={16} /><span>Sign out</span></button></header>
    <div className="workspace-content assistant-content">
      <section className="assistant-title"><span className="assistant-promo-icon"><Sparkles size={20} /></span><span className="workspace-eyebrow">YOUR AUTHORIZED MEDICAL RECORDS</span><h1>Medical records assistant</h1><p>Ask questions about reports available to your account. Answers include the source evidence returned by the records service.</p></section>

      {error && <div className="workspace-alert" role="alert"><span>{error}</span><button type="button" onClick={() => token && void loadHistory(token, true)}><RefreshCw size={15} /> Retry history</button></div>}

      <section className="rag-filter-panel" aria-labelledby="document-filter-label">
        <div className="rag-filter-heading"><div><strong id="document-filter-label">Search in documents</strong><p>Optional · Only indexed documents can be selected.</p></div><FileText size={16} aria-hidden="true" /></div>
        {documentsLoading ? <p className="rag-filter-message" role="status"><LoaderCircle size={14} className="spin" /> Checking report availability…</p>
          : documentError ? <p className="rag-filter-message" role="status">The report filter is unavailable. You can still search all records.</p>
            : documents.length === 0 ? <p className="rag-filter-message">No uploaded reports are available yet. <Link href="/documents/upload">Upload a report</Link>.</p>
              : <>
                <div className="rag-document-options">
                  {documents.map((document) => {
                    const searchable = isSearchable(document);
                    const checked = selectedDocumentIds.includes(document.id);
                    const inputId = `rag-document-${document.id}`;
                    return <div className={`rag-document-option${searchable ? "" : " is-unavailable"}`} key={document.id}>
                      <input id={inputId} type="checkbox" checked={checked} disabled={!searchable || sending} onChange={() => toggleDocument(document.id)} />
                      <label className="rag-document-label" htmlFor={inputId}>
                        <span className="rag-document-check" aria-hidden="true">{checked && <Check size={13} />}</span>
                        <FileText size={15} aria-hidden="true" />
                        <span className="rag-document-copy"><strong>{document.original_filename}</strong><small>{document.document_type.replaceAll("_", " ")} · {indexDescription(document)}</small></span>
                      </label>
                      {!searchable && <Link href={`/documents/${encodeURIComponent(document.id)}`} className="rag-document-detail">View status</Link>}
                    </div>;
                  })}
                </div>
                <p className="rag-filter-footnote"><span>{documentTotal > documents.length ? `Showing ${documents.length} newest of ${documentTotal} reports. ` : ""}{selectedDocumentIds.length ? `${selectedDocumentIds.length} document${selectedDocumentIds.length === 1 ? "" : "s"} selected` : "No selection searches all your available records."}</span><button type="button" onClick={() => setSelectedDocumentIds([])} disabled={!selectedDocumentIds.length || sending}>Clear</button></p>
              </>}
      </section>

      <section className="chat-panel" aria-label="Medical records assistant conversation">
        <div className="chat-scroll" aria-live="polite" aria-busy={loading || sending}>
          {loading ? <div className="workspace-state"><LoaderCircle size={19} className="spin" /> Loading your conversation…</div>
            : entries.length ? <div className="chat-messages">{entries.map((entry) => <article className="chat-turn" key={entry.id}>
              <div className="chat-question"><span aria-hidden="true">You</span><p>{entry.question}</p></div>
              <div className="chat-answer">
                <span className="chat-assistant-label"><Sparkles size={14} /> {responseLabel(entry.generation_status)}</span>
                {entry.generation_status === "insufficient_evidence" && <p className="rag-mode-notice">The available indexed records do not contain enough evidence to answer this question confidently. Try a narrower question or add the relevant report.</p>}
                {entry.generation_status === "evidence_only" && <p className="rag-mode-notice">Relevant evidence was retrieved. Conversational answer generation is unavailable, so review the source excerpts below.</p>}
                <p className="chat-answer-text">{entry.answer}</p>
                <SourceList citations={entry.citations} evidence={entry.evidence} />
                {!entry.citations.length && entry.generation_status !== "insufficient_evidence" && <p className="chat-no-citations">No source citations were returned for this response.</p>}
              </div>
            </article>)}</div>
            : <div className="chat-empty"><span><MessageCircle size={22} /></span><h2>Ask about your medical records</h2><p>{documents.some(isSearchable) ? "Suggestions reflect the indexed report types available to your account. Answers are based on records the backend retrieves." : "Upload and wait for a report to finish indexing before asking questions about it."}</p>{suggestedQuestions(documents).length > 0 && <div className="chat-suggestions">{suggestedQuestions(documents).map((suggestion) => <button type="button" key={suggestion} onClick={() => { setQuestion(suggestion); input.current?.focus(); }}>{suggestion}</button>)}</div>}</div>}
          {sending && <div className="chat-working" role="status"><LoaderCircle size={16} className="spin" /> Searching your available medical records…</div>}
        </div>
        <form className="chat-composer" onSubmit={(event) => void submit(event)}>
          <label className="sr-only" htmlFor="health-question">Ask a question about your records</label>
          <textarea ref={input} id="health-question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask about your medical records…" maxLength={1000} rows={2} disabled={sending} aria-describedby="question-help" />
          <button type="submit" aria-label="Send question" disabled={sending || !question.trim()}>{sending ? <LoaderCircle size={17} className="spin" /> : <ArrowUp size={18} />}</button>
          <small id="question-help">Enter to send · Shift + Enter for a new line · Up to 1,000 characters</small>
        </form>
      </section>
      <p className="assistant-disclaimer"><ShieldCheck size={14} /> This assistant provides informational support from retrieved records; it does not diagnose or recommend treatment. Contact a qualified clinician for medical advice.</p>
      <footer className="workspace-footer"><button className="workspace-text-button" onClick={() => token && void loadHistory(token, true)} disabled={loading}><RefreshCw size={14} /> Refresh saved conversation</button><span>Saved to your account by the backend</span></footer>
    </div>
  </main>;
}
