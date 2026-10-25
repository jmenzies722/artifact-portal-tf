// Thin client for the artifacts API. Every call carries the Cognito access
// token; the API (not this UI) is what actually enforces permissions.

import { getAccessToken, signOut } from "./auth";
import type { PortalConfig } from "./config";

export type FileItem = { key: string; size: number; last_modified: string };
export type ListResponse = { prefixes: string[]; items: FileItem[]; truncated: boolean };
export type DownloadResponse = { url: string; key: string; expires_in: number };
export type UploadResponse = {
  url: string;
  key: string;
  expires_in: number;
  required_headers: Record<string, string>;
};

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function friendlyMessage(status: number, serverMessage?: string): string {
  if (status === 403) return "You don't have access to this folder";
  if (status === 404) return "That file no longer exists.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return "Something went wrong on our side. Please try again.";
  return serverMessage || `Request failed (HTTP ${status}).`;
}

async function call<T>(
  cfg: PortalConfig,
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const token = await getAccessToken(cfg);
  if (!token) {
    signOut(cfg);
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${cfg.apiBase}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "Couldn't reach the server. Check your connection and try again.");
  }

  if (res.status === 401) {
    signOut(cfg);
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new ApiError(res.status, friendlyMessage(res.status, body.error));
  }
  return (await res.json()) as T;
}

const q = (name: string, value: string) => `${name}=${encodeURIComponent(value)}`;

export const api = {
  list: (cfg: PortalConfig, prefix: string) =>
    call<ListResponse>(cfg, prefix ? `/files?${q("prefix", prefix)}` : "/files"),

  downloadUrl: (cfg: PortalConfig, key: string) =>
    call<DownloadResponse>(cfg, `/download?${q("key", key)}`),

  createUpload: (cfg: PortalConfig, key: string, contentType: string) =>
    call<UploadResponse>(cfg, "/upload", { method: "POST", body: { key, content_type: contentType } }),

  remove: (cfg: PortalConfig, key: string) =>
    call<{ deleted: string }>(cfg, `/files?${q("key", key)}`, { method: "DELETE" }),
};

/**
 * PUT the file to its presigned S3 URL with exactly the headers the API
 * signed (Content-Type, SSE-KMS, If-None-Match). XHR rather than fetch
 * because only XHR reports upload progress.
 */
export function putToS3(
  upload: UploadResponse,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", upload.url);
    for (const [name, value] of Object.entries(upload.required_headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(1);
        resolve();
      } else if (xhr.status === 412) {
        reject(new ApiError(412, "This version already exists. Artifacts are immutable."));
      } else if (xhr.status === 403) {
        reject(new ApiError(403, "The upload link expired or was rejected. Please try again."));
      } else {
        reject(new ApiError(xhr.status, `Upload failed (HTTP ${xhr.status}).`));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Upload failed. Check your connection and try again."));
    xhr.send(file);
  });
}
