// Runtime config, fetched from /config.json. Terraform writes the real file
// into the site bucket, so one build works in every environment.

export type PortalConfig = {
  apiBase: string;
  cognitoDomain: string;
  clientId: string;
  redirectUri: string;
  logoutUri: string;
  region: string;
};

const KEYS: (keyof PortalConfig)[] = [
  "apiBase",
  "cognitoDomain",
  "clientId",
  "redirectUri",
  "logoutUri",
  "region",
];

let pending: Promise<PortalConfig> | null = null;

async function fetchConfig(): Promise<PortalConfig> {
  const res = await fetch("/config.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`Couldn't load /config.json (HTTP ${res.status}).`);
  const raw = (await res.json()) as Record<string, unknown>;
  for (const key of KEYS) {
    if (typeof raw[key] !== "string" || !raw[key]) {
      throw new Error(`/config.json is missing "${key}".`);
    }
  }
  const cfg = raw as PortalConfig;
  const trim = (s: string) => s.replace(/\/+$/, "");
  return { ...cfg, apiBase: trim(cfg.apiBase), cognitoDomain: trim(cfg.cognitoDomain) };
}

export function loadConfig(): Promise<PortalConfig> {
  pending ??= fetchConfig().catch((err: unknown) => {
    pending = null; // let a later call retry
    throw err;
  });
  return pending;
}
