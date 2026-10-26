"use client";

import { Bot, ChevronDown, CloudDownload, CloudUpload, History, RefreshCw, Trash2, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type ActivityItem } from "@/lib/api";
import type { PortalConfig } from "@/lib/config";
import { absoluteTime, cx, relativeTime } from "@/lib/format";
import { Button } from "../ui";

const ACTIONS: Record<ActivityItem["action"], { icon: LucideIcon; verb: string; tone: string }> = {
  upload: { icon: CloudUpload, verb: "uploaded", tone: "text-accent" },
  download: { icon: CloudDownload, verb: "downloaded", tone: "text-success" },
  delete: { icon: Trash2, verb: "deleted", tone: "text-danger" },
};

const RANGES = [
  { days: 1, label: "24h" },
  { days: 7, label: "7 days" },
];

const fileName = (key: string) => key.split("/").filter(Boolean).pop() ?? key;

/**
 * The API returns only events for files the caller may list, so this panel
 * never filters anything itself. `version` bumps after the user's own
 * upload/download/delete so their action shows up without a manual refresh.
 */
export function ActivityPanel({ config, version }: { config: PortalConfig; version: number }) {
  const [open, setOpen] = useState(true);
  const [days, setDays] = useState(1);
  const [items, setItems] = useState<ActivityItem[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const latestRequest = useRef(0);

  const load = useCallback(async () => {
    const id = ++latestRequest.current;
    setLoading(true);
    try {
      const res = await api.activity(config, days);
      if (id === latestRequest.current) {
        setItems(res.items);
        setError(null);
      }
    } catch (err) {
      if (id === latestRequest.current) setError(err instanceof ApiError ? err : new ApiError(0, String(err)));
    } finally {
      if (id === latestRequest.current) setLoading(false);
    }
  }, [config, days]);

  useEffect(() => {
    void load();
  }, [load, version]);

  // No list access means no feed: hide rather than show an error the user can't act on.
  if (error?.status === 403) return null;

  let body: ReactNode;
  if (error) {
    body = (
      <div className="flex items-center justify-between gap-3 px-4 py-4 text-sm text-muted">
        <span>Couldn&apos;t load activity. {error.message}</span>
        <Button size="sm" onClick={() => void load()}>Try again</Button>
      </div>
    );
  } else if (items === null) {
    body = (
      <ul aria-hidden className="divide-y divide-border">
        {[0, 1, 2].map((i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-3">
            <div className="size-7 animate-pulse rounded-full bg-elevated" />
            <div className="h-3 flex-1 animate-pulse rounded bg-elevated" />
          </li>
        ))}
      </ul>
    );
  } else if (!items.length) {
    body = (
      <div className="flex flex-col items-center px-6 py-8 text-center">
        <History className="size-5 text-subtle" aria-hidden />
        <p className="mt-2 text-sm font-medium">Nothing yet</p>
        <p className="mt-1 max-w-xs text-sm text-muted">
          Uploads, downloads and deletes in your folders from the last {days === 1 ? "24 hours" : `${days} days`} will show up here.
        </p>
      </div>
    );
  } else {
    body = (
      <ul className="max-h-80 divide-y divide-border overflow-y-auto">
        {items.map((it) => {
          const { icon: Icon, verb, tone } = ACTIONS[it.action] ?? ACTIONS.upload;
          return (
            <li key={`${it.ts}-${it.key}-${it.action}`} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className={cx("flex size-7 shrink-0 items-center justify-center rounded-full bg-elevated", tone)}>
                <Icon className="size-3.5" aria-hidden />
              </span>
              <p className="min-w-0 flex-1 truncate">
                <span className="inline-flex items-center gap-1 font-medium">
                  {it.actor_kind === "machine" && <Bot className="size-3.5 text-subtle" aria-label="CI client" />}
                  {it.actor}
                </span>{" "}
                <span className="text-muted">{verb}</span>{" "}
                <span title={it.key} className="font-mono text-xs">{fileName(it.key)}</span>
              </p>
              <time dateTime={it.ts} title={absoluteTime(it.ts)} className="shrink-0 text-xs text-subtle">
                {relativeTime(it.ts)}
              </time>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <section aria-labelledby="activity-heading" className="mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-sm shadow-black/[0.03]">
      <header className={cx("flex items-center justify-between gap-2 px-4 py-2.5", open && "border-b border-border")}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="activity-body"
          className="flex items-center gap-2 rounded-md text-sm font-medium"
        >
          <ChevronDown className={cx("size-4 text-subtle transition-transform", !open && "-rotate-90")} aria-hidden />
          <span id="activity-heading">Recent activity</span>
        </button>
        {open && (
          <div className="flex items-center gap-1">
            <div role="group" aria-label="Time range" className="flex rounded-lg border border-border p-0.5">
              {RANGES.map((r) => (
                <button
                  key={r.days}
                  type="button"
                  aria-pressed={days === r.days}
                  onClick={() => setDays(r.days)}
                  className={cx(
                    "rounded-md px-2 py-0.5 text-xs transition-colors",
                    days === r.days ? "bg-elevated font-medium text-fg" : "text-muted hover:text-fg",
                  )}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <Button variant="ghost" size="sm" onClick={() => void load()} aria-label="Refresh activity" disabled={loading}>
              <RefreshCw className={cx("size-3.5", loading && "animate-spin")} aria-hidden />
            </Button>
          </div>
        )}
      </header>
      <div id="activity-body" hidden={!open}>{body}</div>
    </section>
  );
}
