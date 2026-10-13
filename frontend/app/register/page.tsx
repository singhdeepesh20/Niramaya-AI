"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { GoogleButton } from "@/components/google-button";
import { ApiError, authApi } from "@/lib/api";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match." });
      return;
    }
    if (!acceptedTerms) {
      setError("Please agree to the Terms of Service and Privacy Policy to continue.");
      return;
    }
    setLoading(true);
    try {
      await authApi.register({ username: username.trim(), email: email.trim(), password });
      sessionStorage.setItem("niramaya_registered", "1");
      window.location.assign("/login?registered=1");
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(cause.message);
        setFieldErrors(cause.fields);
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  const mismatch = Boolean(confirmPassword) && confirmPassword !== password;

  return (
    <AuthLayout mode="register">
      <div className="auth-card register-card">
        <span className="card-kicker">GET STARTED FOR FREE</span>
        <h2>Create Your Account</h2>
        <p className="card-subtitle">Join Niramaya-AI to manage your health records with the power of AI.</p>
        <form onSubmit={submit} noValidate>
          <label className="field-label" htmlFor="username">Username</label>
          <div className={`input-wrap ${fieldErrors.username ? "has-error" : ""}`}><UserRound size={18} aria-hidden="true" /><input id="username" name="username" autoComplete="username" placeholder="Choose a username" required minLength={3} maxLength={30} pattern="[A-Za-z0-9_]+" value={username} onChange={(event) => setUsername(event.target.value)} aria-invalid={Boolean(fieldErrors.username)} aria-describedby={fieldErrors.username ? "username-error" : "username-help"} /></div>
          <small className="field-help" id="username-help">3–30 letters, numbers, or underscores</small>
          {fieldErrors.username && <small className="field-error" id="username-error">{fieldErrors.username}</small>}
          <label className="field-label" htmlFor="email">Email Address</label>
          <div className={`input-wrap ${fieldErrors.email ? "has-error" : ""}`}><Mail size={18} aria-hidden="true" /><input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(fieldErrors.email)} /></div>
          {fieldErrors.email && <small className="field-error">{fieldErrors.email}</small>}
          <label className="field-label" htmlFor="password">Password</label>
          <div className={`input-wrap ${fieldErrors.password ? "has-error" : ""}`}><LockKeyhole size={18} aria-hidden="true" /><input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Create a strong password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={Boolean(fieldErrors.password)} aria-describedby="password-help" /><button className="visibility-button" type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
          <small className="field-help" id="password-help">Use 12–128 characters.</small>
          {fieldErrors.password && <small className="field-error">{fieldErrors.password}</small>}
          <label className="field-label" htmlFor="confirm-password">Confirm Password</label>
          <div className={`input-wrap ${mismatch ? "has-error" : ""}`}><LockKeyhole size={18} aria-hidden="true" /><input id="confirm-password" name="confirm-password" type={showConfirm ? "text" : "password"} autoComplete="new-password" placeholder="Re-enter your password" required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} aria-invalid={mismatch || Boolean(fieldErrors.confirmPassword)} aria-describedby={mismatch ? "confirm-error" : undefined} /><button className="visibility-button" type="button" onClick={() => setShowConfirm((visible) => !visible)} aria-label={showConfirm ? "Hide password" : "Show password"}>{showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
          {(mismatch || fieldErrors.confirmPassword) && <small className="field-error" id="confirm-error">{fieldErrors.confirmPassword || "Passwords do not match."}</small>}
          <label className="agreement"><input type="checkbox" checked={acceptedTerms} onChange={(event) => setAcceptedTerms(event.target.checked)} /><span>I agree to the <Link href="/terms">Terms of Service</Link> and <Link href="/privacy">Privacy Policy</Link></span></label>
          {error && <p className="form-alert" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={loading || !username.trim() || !email.trim() || password.length < 12 || !confirmPassword || mismatch || !acceptedTerms}>{loading ? <><span className="spinner" /> Creating account…</> : <>Create Account <ArrowRight size={17} /></>}</button>
        </form>
        <div className="separator"><span>OR</span></div>
        <GoogleButton />
        <p className="terms-copy">Your health information stays private and under your control.</p>
      </div>
    </AuthLayout>
  );
}
