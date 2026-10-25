"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as auth from "@/lib/auth";
import { loadConfig, type PortalConfig } from "@/lib/config";
import { ToastProvider } from "./toast";

type Portal = {
  /** Config + session have been read on the client. */
  ready: boolean;
  config: PortalConfig | null;
  configError: string | null;
  user: auth.User | null;
  signIn: () => void;
  signOut: () => void;
};

const PortalContext = createContext<Portal | null>(null);

export function usePortal(): Portal {
  const ctx = useContext(PortalContext);
  if (!ctx) throw new Error("usePortal must be used inside <Providers>");
  return ctx;
}

const REFRESH_LEAD_MS = 2 * 60_000;

export function Providers({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PortalConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [session, setSession] = useState<auth.Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSession(auth.getSession());
    const unsubscribe = auth.subscribe(() => setSession(auth.getSession()));
    loadConfig()
      .then(setConfig)
      .catch((err: unknown) => setConfigError(err instanceof Error ? err.message : String(err)))
      .finally(() => setReady(true));
    return unsubscribe;
  }, []);

  // Refresh quietly a couple of minutes before the access token expires.
  useEffect(() => {
    if (!config || !session) return;
    const wait = Math.max(0, session.expiresAt - Date.now() - REFRESH_LEAD_MS);
    const timer = window.setTimeout(() => void auth.refreshSession(config), wait);
    return () => window.clearTimeout(timer);
  }, [config, session]);

  const signIn = useCallback(() => {
    if (config) void auth.signIn(config);
  }, [config]);

  const signOut = useCallback(() => {
    if (config) auth.signOut(config);
    else auth.clearSession();
  }, [config]);

  const value = useMemo<Portal>(
    () => ({ ready, config, configError, user: auth.userFromSession(session), signIn, signOut }),
    [ready, config, configError, session, signIn, signOut],
  );

  return (
    <PortalContext.Provider value={value}>
      <ToastProvider>{children}</ToastProvider>
    </PortalContext.Provider>
  );
}
