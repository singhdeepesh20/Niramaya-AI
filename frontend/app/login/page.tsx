"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { GoogleButton } from "@/components/google-button";
import { ApiError, authApi } from "@/lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("niramaya_registered") === "1") {
      setRegistered(true);
      sessionStorage.removeItem("niramaya_registered");
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await authApi.login({ username: username.trim(), password });
      // Current backend contract is a bearer token; retain it in tab-scoped memory storage only.
      sessionStorage.removeItem("niramaya_user_cache");
      sessionStorage.setItem("niramaya_access_token", result.access_token);
      window.location.assign("/dashboard");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Sign in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout mode="login">
      <div className="auth-card login-card">
        <span className="card-kicker">YOUR HEALTH, IN ONE PLACE</span>
        <h2>Welcome Back</h2>
        <p className="card-subtitle">Sign in to your Niramaya-AI account</p>
        {registered && <p className="form-success" role="status">Your account is ready. Sign in to continue.</p>}
        <form onSubmit={submit} noValidate>
          <label className="field-label" htmlFor="username">Username</label>
          <div className="input-wrap"><UserRound size={18} aria-hidden="true" /><input id="username" name="username" autoComplete="username" placeholder="Your username" required minLength={3} maxLength={30} value={username} onChange={(event) => setUsername(event.target.value)} /></div>
          <div className="password-label-row"><label className="field-label" htmlFor="password">Password</label><span className="muted-link" title="Password recovery is not configured yet">Forgot password?</span></div>
          <div className="input-wrap"><LockKeyhole size={18} aria-hidden="true" /><input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /><button className="visibility-button" type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
          {error && <p className="form-alert" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={loading || !username.trim() || password.length < 12}>{loading ? <><span className="spinner" /> Signing in…</> : <>Sign In <ArrowRight size={17} /></>}</button>
        </form>
        <div className="separator"><span>OR</span></div>
        <GoogleButton />
        <p className="terms-copy">By continuing, you agree to our <Link href="/terms">Terms of Service</Link> and <Link href="/privacy">Privacy Policy</Link>.</p>
      </div>
    </AuthLayout>
  );
}
