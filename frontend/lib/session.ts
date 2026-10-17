"use client";

import { ApiError, authApi } from "@/lib/api";

type Router = { replace: (href: string) => void };

const TOKEN_KEY = "niramaya_access_token";

export function readAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function clearSession(router?: Router): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem("niramaya_registered");
  sessionStorage.removeItem("niramaya_user_cache");
  authApi.logout().catch(() => {});
  if (router) router.replace("/login");
}

export function handleSessionError(error: unknown, router: Router): string {
  if (error instanceof ApiError && error.status === 401) {
    clearSession(router);
    return "Your session has expired. Please sign in again.";
  }
  return error instanceof ApiError ? error.message : "The request could not be completed. Please try again.";
}
