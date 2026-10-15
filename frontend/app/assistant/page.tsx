"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, FileText, LoaderCircle, LogOut, MessageCircle, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { ApiError, ChatHistoryItem, Citation, EvidenceItem, healthApi } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";
import { clearSession, handleSessionError, readAccessToken } from "@/lib/session";

type ChatEntry = { id: string; question: string; answer: string; citations: Citation[]; evidence?: EvidenceItem[]; created_at: string; generation_status?: string };

function historyEntry(item: ChatHistoryItem): ChatEntry { return { ...item }; }

export default function AssistantPage() {
  const router = useRouter();
  const input = useRef<HTMLTextAreaElement>(null);
  const [token, setToken] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory(authToken: string) {
    setLoading(true); setError("");
    try { setEntries((await healthApi.history(authToken)).map(historyEntry)); }
    catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setError(handleSessionError(cause, router));
    } finally { setLoading(false); }
  }

  useEffect(() => {
    const saved = readAccessToken();
    if (!saved) { router.replace("/login"); return; }
    setToken(saved); void loadHistory(saved);
    // Initial session load only; history refresh is explicit after a successful answer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!token || !cleanQuestion || sending) return;
    setSending(true); setError(""); setQuestion("");
    try {
      const result = await healthApi.ask(token, cleanQuestion);
      setEntries((current) => [{
        id: `reply-${Date.now()}`,
        question: cleanQuestion,
        answer: result.answer,
        citations: result.citations,
        evidence: result.evidence,
        generation_status: result.generation_status,
        created_at: new Date().toISOString(),
      }, ...current]);
      input.current?.focus();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { clearSession(router); return; }
      setError(handleSessionError(cause, router));
      setQuestion(cleanQuestion);
    } finally { setSending(false); }
  }

  return <main className="workspace-page assistant-page">
    <header className="workspace-header"><Link className="brand" href="/dashboard"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></Link><nav aria-label="Main navigation"><Link href="/dashboard">Overview</Link><Link href="/documents">My documents</Link><Link className="workspace-nav-active" href="/assistant">Health assistant</Link></nav><button className="workspace-signout" onClick={() => clearSession(router)}><LogOut size={16} /><span>Sign out</span></button></header>
    <div className="workspace-content assistant-content">
      <section className="assistant-title"><span className="assistant-promo-icon"><Sparkles size={20} /></span><span className="workspace-eyebrow">YOUR AUTHORIZED MEDICAL RECORDS</span><h1>Health assistant</h1><p>Ask a question about reports available to your account. Answers and citations come from the backend.</p></section>
      {error && <div className="workspace-alert" role="alert"><span>{error}</span><button onClick={() => token && void loadHistory(token)}><RefreshCw size={15} /> Retry</button></div>}
      <section className="chat-panel" aria-label="Health assistant conversation">
        <div className="chat-scroll" aria-live="polite">
          {loading ? <div className="workspace-state"><LoaderCircle size={19} className="spin" /> Loading your conversation…</div>
            : entries.length ? <div className="chat-messages">{entries.map((entry) => <article className="chat-turn" key={entry.id}>
              <div className="chat-question"><span>You</span><p>{entry.question}</p></div>
              <div className="chat-answer"><span className="chat-assistant-label"><Sparkles size={14} /> {entry.generation_status === "evidence_only" ? "Authorized evidence" : "Niramaya-AI"}</span><p className="chat-answer-text">{entry.answer}</p>
                {entry.citations.length > 0 && <div className="chat-citations"><strong>Sources returned by the assistant</strong>{entry.citations.map((citation, index) => <Link key={`${entry.id}-${citation.document_id}-${citation.page_number}-${index}`} href={`/documents/${citation.document_id}`} className="chat-citation"><FileText size={15} /><span>{citation.document_name}{citation.page_number ? ` · Page ${citation.page_number}` : ""}</span></Link>)}</div>}
                {entry.evidence?.length ? <div className="chat-citations"><strong>Retrieved evidence</strong>{entry.evidence.map((item, index) => <Link key={`${entry.id}-evidence-${index}`} href={`/documents/${item.document_id}`} className="chat-citation"><FileText size={15} /><span>{item.document_name}{item.page_number ? ` · Page ${item.page_number}` : ""}: {item.excerpt}</span></Link>)}</div> : null}
                {!entry.citations.length && <p className="chat-no-citations">No citations were returned for this response.</p>}
              </div>
            </article>)}</div>
            : <div className="chat-empty"><span><MessageCircle size={22} /></span><h2>What would you like to understand?</h2><p>Ask about information in your uploaded reports. If your records do not contain an answer, the assistant will say so.</p><div className="chat-suggestions"><button onClick={() => setQuestion("What information is available in my reports?")}>What information is in my reports?</button><button onClick={() => setQuestion("What was my latest hemoglobin result?")}>What was my latest hemoglobin result?</button></div></div>}
          {sending && <div className="chat-working" role="status"><LoaderCircle size={16} className="spin" /> Checking authorized records…</div>}
        </div>
        <form className="chat-composer" onSubmit={(event) => void submit(event)}><label className="sr-only" htmlFor="health-question">Ask a question about your records</label><textarea ref={input} id="health-question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask about your medical records…" maxLength={1000} rows={2} disabled={sending} /><button type="submit" aria-label="Send question" disabled={sending || !question.trim()}>{sending ? <LoaderCircle size={17} className="spin" /> : <ArrowUp size={18} />}</button><small>Enter to send · Shift + Enter for a new line</small></form>
      </section>
      <p className="assistant-disclaimer"><ShieldCheck size={14} /> This assistant provides informational support from authorized records, not a diagnosis or treatment plan. For medical advice, contact a qualified clinician.</p>
      <footer className="workspace-footer"><button className="workspace-text-button" onClick={() => token && void loadHistory(token)}><RefreshCw size={14} /> Refresh conversation</button></footer>
    </div>
  </main>;
}
