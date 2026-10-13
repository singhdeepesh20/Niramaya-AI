"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, LogOut, ShieldCheck } from "lucide-react";
import { ApiError, authApi, User } from "@/lib/api";
import { BrandMark } from "@/components/auth-layout";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = sessionStorage.getItem("niramaya_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    authApi.me(token).then(setUser).catch((cause: unknown) => {
      sessionStorage.removeItem("niramaya_access_token");
      setError(cause instanceof ApiError ? cause.message : "Your session could not be verified.");
      router.replace("/login");
    });
  }, [router]);

  function signOut() {
    sessionStorage.removeItem("niramaya_access_token");
    router.replace("/login");
  }

  return (
    <main className="dashboard-page">
      <header className="dashboard-header"><a className="brand" href="/login"><BrandMark /><span><strong>Niramaya-AI</strong><small>Your Health Records. Smarter.</small></span></a><button className="signout-button" onClick={signOut}><LogOut size={16} /> Sign out</button></header>
      <section className="dashboard-welcome">
        <span className="dashboard-icon"><Activity size={23} /></span>
        <p className="card-kicker">YOUR PERSONAL HEALTH SPACE</p>
        <h1>Welcome{user ? `, ${user.username}` : ""}</h1>
        <p>{error || (user ? "You’re signed in. Your account is ready for your health journey." : "Checking your secure session…")}</p>
        {user && <div className="account-chip"><ShieldCheck size={16} /> Signed in as <b>{user.email}</b></div>}
      </section>
    </main>
  );
}
