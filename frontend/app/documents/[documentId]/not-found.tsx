import Link from "next/link";

export default function DocumentNotFound() {
  return <main className="workspace-page"><section className="workspace-panel workspace-empty detail-not-found"><span aria-hidden="true">?</span><h1>Report unavailable</h1><p>This report may have been removed or may not be available to your account.</p><Link className="workspace-secondary" href="/documents">Return to documents</Link></section></main>;
}
