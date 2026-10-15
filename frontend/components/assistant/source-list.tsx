import Link from "next/link";
import { ArrowUpRight, FileText, Quote } from "lucide-react";
import type { Citation, EvidenceItem } from "@/lib/api";

type Props = { citations: Citation[]; evidence: EvidenceItem[] };

export function SourceList({ citations, evidence }: Props) {
  if (!citations.length && !evidence.length) return null;

  const evidenceBySource = new Map<string, EvidenceItem[]>();
  for (const item of evidence) {
    const group = evidenceBySource.get(item.document_id) ?? [];
    group.push(item);
    evidenceBySource.set(item.document_id, group);
  }

  return <section className="rag-sources" aria-label="Sources and retrieved evidence">
    <h3>Sources from your records</h3>
    {(citations.length ? citations : evidence).map((citation, index) => {
      const sourceEvidence = (evidenceBySource.get(citation.document_id) ?? []).filter((item) =>
        citation.page_number === null || item.page_number === citation.page_number,
      );
      const uniqueKey = `${citation.document_id}-${citation.page_number ?? "no-page"}-${index}`;
      return <article className="rag-source-card" key={uniqueKey}>
        <div className="rag-source-heading">
          <span className="rag-source-icon" aria-hidden="true"><FileText size={15} /></span>
          <div className="rag-source-title">
            <strong>{citation.document_name || "Medical document"}</strong>
            <small>{citation.page_number ? `Page ${citation.page_number}` : "Page not provided"}</small>
          </div>
          <Link href={`/documents/${encodeURIComponent(citation.document_id)}`} className="rag-source-link">
            Open report <ArrowUpRight size={13} aria-hidden="true" />
          </Link>
        </div>
        {sourceEvidence.map((item, excerptIndex) => <blockquote className="rag-evidence-excerpt" key={`${uniqueKey}-e${excerptIndex}`}>
          <Quote size={13} aria-hidden="true" />
          <p>{item.excerpt}</p>
        </blockquote>)}
      </article>;
    })}
  </section>;
}
