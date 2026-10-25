"use client";

import { CircleAlert, CircleCheck, LoaderCircle, X } from "lucide-react";
import { cx } from "@/lib/format";

export type Upload = {
  id: number;
  name: string;
  key: string;
  progress: number; // 0..1
  status: "uploading" | "done" | "error";
  error?: string;
};

export function UploadPanel({ uploads, onClear }: { uploads: Upload[]; onClear: () => void }) {
  if (!uploads.length) return null;
  const active = uploads.filter((u) => u.status === "uploading").length;

  return (
    <section
      aria-label="Uploads"
      className="animate-toast-in fixed bottom-4 left-4 right-4 z-40 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl shadow-black/20 sm:right-auto sm:w-80"
    >
      <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <p className="text-sm font-medium">
          {active ? `Uploading ${active} file${active === 1 ? "" : "s"}…` : "Uploads complete"}
        </p>
        <button
          type="button"
          onClick={onClear}
          disabled={active > 0}
          aria-label="Clear finished uploads"
          className="rounded-md p-1 text-subtle transition-colors hover:bg-elevated hover:text-fg disabled:opacity-40"
        >
          <X className="size-4" aria-hidden />
        </button>
      </header>
      <ul className="max-h-64 divide-y divide-border overflow-y-auto">
        {uploads.map((u) => (
          <li key={u.id} className="px-4 py-3">
            <div className="flex items-center gap-2">
              {u.status === "uploading" && <LoaderCircle className="size-3.5 shrink-0 animate-spin text-accent" aria-hidden />}
              {u.status === "done" && <CircleCheck className="size-3.5 shrink-0 text-success" aria-hidden />}
              {u.status === "error" && <CircleAlert className="size-3.5 shrink-0 text-danger" aria-hidden />}
              <span className="min-w-0 flex-1 truncate text-sm" title={u.key}>{u.name}</span>
              <span className="shrink-0 text-xs tabular-nums text-subtle">
                {u.status === "uploading" ? `${Math.round(u.progress * 100)}%` : u.status === "done" ? "Done" : "Failed"}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={`Upload progress for ${u.name}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(u.progress * 100)}
              className="mt-2 h-1 overflow-hidden rounded-full bg-elevated"
            >
              <div
                className={cx(
                  "h-full rounded-full transition-[width] duration-200",
                  u.status === "error" ? "bg-danger" : u.status === "done" ? "bg-success" : "bg-accent",
                )}
                style={{ width: `${u.status === "error" ? 100 : Math.max(2, u.progress * 100)}%` }}
              />
            </div>
            {u.error && <p className="mt-1.5 text-xs text-danger">{u.error}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
