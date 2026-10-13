import Link from "next/link";
import { Activity, BrainCircuit, FileUp, LockKeyhole, ShieldCheck } from "lucide-react";

const features = [
  { icon: FileUp, title: "Upload Reports", text: "CBC, MRI, prescriptions, discharge summaries, and more" },
  { icon: BrainCircuit, title: "AI-Powered Insights", text: "Find answers, patterns and important health information" },
  { icon: ShieldCheck, title: "Secure & Private", text: "Your data stays yours, always" },
];

export function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><Activity size={21} strokeWidth={2.2} /></span>;
}

export function AuthLayout({ mode, children }: { mode: "login" | "register"; children: React.ReactNode }) {
  const register = mode === "register";
  return (
    <main className={`auth-page ${register ? "register-page" : "login-page"}`}>
      <section className="hero-panel" aria-label="About Niramaya-AI">
        <Link href="/login" className="brand" aria-label="Niramaya-AI home">
          <BrandMark />
          <span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span>
        </Link>
        <div className="hero-copy">
          <span className="eyebrow"><span className="pulse-dot" /> A clearer view of your health</span>
          <h1>Your Health Data,<br /><em>Understandable</em><br />at Last</h1>
          <p>Niramaya-AI turns scattered medical reports into a single, intelligent health record — so you can search, understand and take control of your health.</p>
        </div>
        <div className="feature-list">
          {features.map(({ icon: Icon, title, text }) => (
            <div className="feature-row" key={title}>
              <span className="feature-icon"><Icon size={19} strokeWidth={1.8} /></span>
              <span><strong>{title}</strong><small>{text}</small></span>
            </div>
          ))}
        </div>
        <div className="medical-art" aria-hidden="true">
          <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
          <div className="report-card report-main">
            <div className="report-top"><span className="mini-mark"><Activity size={13} /></span><span><b>Health summary</b><small>Updated just now</small></span><span className="report-menu">•••</span></div>
            <div className="summary-line"><span className="summary-icon"><Activity size={14} /></span><span><b>Labs & Reports</b><small>12 documents</small></span><span className="summary-chevron">↗</span></div>
            <div className="summary-line"><span className="summary-icon blue"><BrainCircuit size={14} /></span><span><b>Medications</b><small>3 active</small></span><span className="summary-chevron">↗</span></div>
            <div className="summary-line"><span className="summary-icon gold"><Activity size={14} /></span><span><b>Health timeline</b><small>Updated recently</small></span><span className="summary-chevron">↗</span></div>
            <div className="chart-bars"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
          </div>
          <div className="report-card report-float"><span className="float-icon"><FileUp size={17} /></span><span><b>Lab report</b><small>Blood panel · PDF</small></span><span className="float-check">✓</span></div>
          <div className="security-float"><LockKeyhole size={16} /><span>Private by design</span></div>
          <div className="art-glow" />
        </div>
        <footer className="hero-footer"><ShieldCheck size={14} /> HIPAA-inspired security <span>·</span> Your data, your control</footer>
      </section>
      <section className="form-panel">
        <div className="form-panel-inner">
          <nav className="top-nav" aria-label="Account navigation">
            {register ? <span>Already have an account? <Link href="/login">Sign in <span aria-hidden="true">→</span></Link></span> : <span>New here? <Link href="/register">Create an account <span aria-hidden="true">→</span></Link></span>}
          </nav>
          {children}
          <div className="mobile-brand"><BrandMark /><span><b>Niramaya-AI</b><small>Your Health Records. Smarter.</small></span></div>
        </div>
      </section>
    </main>
  );
}
