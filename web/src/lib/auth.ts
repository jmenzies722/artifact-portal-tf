// Cognito hosted UI, authorization code + PKCE (public client, no secret).
// Tokens live in memory and sessionStorage only: they die with the tab and
// are never written to localStorage.

import type { PortalConfig } from "./config";

const PKCE_KEY = "ap.pkce";
const SESSION_KEY = "ap.session";
const SKEW_MS = 60_000; // treat tokens as expired a minute early

export type Session = {
  idToken: string;
  accessToken: string;
  refreshToken?: string;
  expiresAt: number; // epoch ms
};

export type User = {
  sub: string;
  email: string;
  groups: string[];
};

type TokenResponse = {
  id_token: string;
  access_token: string;
  refresh_token?: string;
  expires_in: number;
};

// ---- encoding helpers ------------------------------------------------------

function base64Url(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(byteLength: number): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

async function s256(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}

export function decodeJwt(token: string): Record<string, unknown> {
  const part = token.split(".")[1] ?? "";
  const b64 = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
}

// ---- session store ----------------------------------------------------------

let memory: Session | null = null;
const listeners = new Set<() => void>();

export function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit() {
  for (const fn of listeners) fn();
}

export function getSession(): Session | null {
  if (memory || typeof window === "undefined") return memory;
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    memory = JSON.parse(raw) as Session;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
  }
  return memory;
}

function saveSession(tokens: TokenResponse, previousRefresh?: string): Session {
  memory = {
    idToken: tokens.id_token,
    accessToken: tokens.access_token,
    // Cognito doesn't return a new refresh token on refresh; keep the old one.
    refreshToken: tokens.refresh_token ?? previousRefresh,
    expiresAt: Date.now() + tokens.expires_in * 1000,
  };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(memory));
  emit();
  return memory;
}

export function clearSession() {
  memory = null;
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(PKCE_KEY);
  emit();
}

export function userFromSession(session: Session | null): User | null {
  if (!session) return null;
  try {
    const claims = decodeJwt(session.idToken);
    const groups = claims["cognito:groups"];
    return {
      sub: String(claims.sub ?? ""),
      email: String(claims.email ?? claims["cognito:username"] ?? "Signed in"),
      groups: Array.isArray(groups) ? groups.map(String) : [],
    };
  } catch {
    return null;
  }
}

// ---- OAuth flows -------------------------------------------------------------

async function tokenRequest(cfg: PortalConfig, params: Record<string, string>): Promise<TokenResponse> {
  const res = await fetch(`${cfg.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: cfg.clientId, ...params }),
  });
  const body = (await res.json().catch(() => ({}))) as Partial<TokenResponse> & {
    error?: string;
    error_description?: string;
  };
  if (!res.ok || !body.access_token || !body.id_token) {
    throw new Error(body.error_description || body.error || `Token request failed (HTTP ${res.status}).`);
  }
  return body as TokenResponse;
}

export async function signIn(cfg: PortalConfig) {
  const verifier = randomString(48);
  const state = randomString(16);
  sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state }));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: cfg.clientId,
    redirect_uri: cfg.redirectUri,
    scope: "openid email profile",
    state,
    code_challenge: await s256(verifier),
    code_challenge_method: "S256",
  });
  window.location.assign(`${cfg.cognitoDomain}/oauth2/authorize?${params}`);
}

// Shared so a double-invoked effect (React strict mode) exchanges the code once.
let exchange: Promise<Session> | null = null;

export function completeSignIn(cfg: PortalConfig, search: URLSearchParams): Promise<Session> {
  exchange ??= (async () => {
    const error = search.get("error");
    if (error) throw new Error(search.get("error_description") || error);

    const raw = sessionStorage.getItem(PKCE_KEY);
    sessionStorage.removeItem(PKCE_KEY);
    const pkce = raw ? (JSON.parse(raw) as { verifier: string; state: string }) : null;
    const code = search.get("code");
    if (!code || !pkce || search.get("state") !== pkce.state) {
      throw new Error("This sign-in link doesn't match your browser session. Please sign in again.");
    }
    const tokens = await tokenRequest(cfg, {
      grant_type: "authorization_code",
      code,
      redirect_uri: cfg.redirectUri,
      code_verifier: pkce.verifier,
    });
    return saveSession(tokens);
  })();
  return exchange;
}

let refreshing: Promise<Session | null> | null = null;

async function doRefresh(cfg: PortalConfig): Promise<Session | null> {
  const current = getSession();
  if (!current?.refreshToken) {
    clearSession();
    return null;
  }
  try {
    const tokens = await tokenRequest(cfg, {
      grant_type: "refresh_token",
      refresh_token: current.refreshToken,
    });
    return saveSession(tokens, current.refreshToken);
  } catch {
    clearSession();
    return null;
  }
}

export function refreshSession(cfg: PortalConfig): Promise<Session | null> {
  // .finally runs asynchronously, so `refreshing` is assigned before it's cleared.
  refreshing ??= doRefresh(cfg).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** A valid access token, refreshing first if it is about to expire. */
export async function getAccessToken(cfg: PortalConfig): Promise<string | null> {
  const session = getSession();
  if (!session) return null;
  if (session.expiresAt - SKEW_MS > Date.now()) return session.accessToken;
  return (await refreshSession(cfg))?.accessToken ?? null;
}

export function signOut(cfg: PortalConfig) {
  clearSession();
  const params = new URLSearchParams({ client_id: cfg.clientId, logout_uri: cfg.logoutUri });
  window.location.assign(`${cfg.cognitoDomain}/logout?${params}`);
}
