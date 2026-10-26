"use client";

import { ChevronRight, CloudUpload, FolderOpen, RefreshCw, Search, ShieldAlert, UserRoundX } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import { api, ApiError, putToS3, type ListResponse } from "@/lib/api";
import type { PortalConfig } from "@/lib/config";
import { cx, folderName } from "@/lib/format";
import { can, knownRoles, prefixesFor, sidebarFolders } from "@/lib/rbac";
import { buildRows, filesHref, normalizePrefix, type FileRow } from "@/lib/tree";
import { ConfirmDialog } from "../confirm-dialog";
import { usePortal } from "../providers";
import { useToast } from "../toast";
import { Button, buttonClass, EmptyState } from "../ui";
import { ActivityPanel } from "./activity-panel";
import { FileTable, TableSkeleton } from "./file-table";
import { Sidebar } from "./sidebar";
import { UploadPanel, type Upload } from "./upload-panel";

const toApiError = (err: unknown) =>
  err instanceof ApiError ? err : new ApiError(0, err instanceof Error ? err.message : String(err));

function Breadcrumb({ prefix }: { prefix: string }) {
  const parts = prefix.split("/").filter(Boolean);
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-muted">
        <li>
          {parts.length ? (
            <Link href={filesHref("")} className="rounded-md hover:text-fg">All files</Link>
          ) : (
            <span aria-current="page" className="text-fg">All files</span>
          )}
        </li>
        {parts.map((part, i) => {
          const p = `${parts.slice(0, i + 1).join("/")}/`;
          const last = i === parts.length - 1;
          return (
            <li key={p} className="flex items-center gap-1">
              <ChevronRight className="size-3.5 text-subtle" aria-hidden />
              {last ? (
                <span aria-current="page" className="text-fg">{part}</span>
              ) : (
                <Link href={filesHref(p)} className="rounded-md hover:text-fg">{part}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function FileBrowser() {
  const { ready, config, user } = usePortal();
  const router = useRouter();
  const prefix = normalizePrefix(useSearchParams()?.get("prefix") ?? null);
  const toast = useToast();

  const groups = useMemo(() => user?.groups ?? [], [user]);
  const signedIn = Boolean(user);
  const hasRole = knownRoles(groups).length > 0;
  const canUpload = can(groups, "write", prefix);

  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [pendingDelete, setPendingDelete] = useState<FileRow | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [activityVersion, setActivityVersion] = useState(0);
  const bumpActivity = () => setActivityVersion((v) => v + 1);

  const dragDepth = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const latestRequest = useRef(0);
  const nextUploadId = useRef(1);

  useEffect(() => {
    if (ready && !signedIn) router.replace("/");
  }, [ready, signedIn, router]);

  const load = useCallback(
    async (quiet = false) => {
      if (!config || !signedIn) return;
      const id = ++latestRequest.current; // ignore responses for folders we've left
      if (!quiet) setLoading(true);
      try {
        const res = await api.list(config, prefix);
        if (id === latestRequest.current) {
          setData(res);
          setError(null);
        }
      } catch (err) {
        if (id === latestRequest.current) {
          setError(toApiError(err));
          setData(null);
        }
      } finally {
        if (id === latestRequest.current) setLoading(false);
      }
    },
    [config, signedIn, prefix],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => setFilter(""), [prefix]);

  const rows = useMemo(() => {
    const all = buildRows(data?.items ?? [], prefix, prefixesFor(groups, "list"));
    const q = filter.trim().toLowerCase();
    return q ? all.filter((r) => r.name.toLowerCase().includes(q)) : all;
  }, [data, prefix, groups, filter]);

  // ---- actions ---------------------------------------------------------------

  const patchUpload = (id: number, patch: Partial<Upload>) =>
    setUploads((all) => all.map((u) => (u.id === id ? { ...u, ...patch } : u)));

  async function uploadOne(cfg: PortalConfig, file: File, key: string, id: number) {
    try {
      const presigned = await api.createUpload(cfg, key, file.type || "application/octet-stream");
      await putToS3(presigned, file, (progress) => patchUpload(id, { progress }));
      patchUpload(id, { status: "done", progress: 1 });
      toast({ tone: "success", title: "Upload complete", description: key });
      void load(true);
      bumpActivity();
    } catch (err) {
      const message = toApiError(err).message;
      patchUpload(id, { status: "error", error: message });
      toast({ tone: "error", title: `Couldn't upload ${file.name}`, description: message });
    }
  }

  function startUploads(files: File[]) {
    if (!config || !files.length) return;
    for (const file of files) {
      const key = `${prefix}${file.name}`;
      const id = nextUploadId.current++;
      setUploads((all) => [...all, { id, name: file.name, key, progress: 0, status: "uploading" }]);
      void uploadOne(config, file, key, id);
    }
  }

  async function download(row: FileRow) {
    if (!config) return;
    setDownloading(row.key);
    try {
      const { url } = await api.downloadUrl(config, row.key);
      const tab = window.open(url, "_blank");
      if (tab) tab.opener = null;
      else window.location.assign(url); // pop-up blocked: download in place
      bumpActivity();
    } catch (err) {
      toast({ tone: "error", title: `Couldn't download ${row.name}`, description: toApiError(err).message });
    } finally {
      setDownloading(null);
    }
  }

  async function confirmDelete() {
    if (!config || !pendingDelete) return;
    const { key, name } = pendingDelete;
    setDeleting(true);
    try {
      await api.remove(config, key);
      setData((d) => d && { ...d, items: d.items.filter((i) => i.key !== key) });
      setPendingDelete(null);
      toast({ tone: "success", title: `Deleted ${name}` });
      void load(true);
      bumpActivity();
    } catch (err) {
      toast({ tone: "error", title: `Couldn't delete ${name}`, description: toApiError(err).message });
    } finally {
      setDeleting(false);
    }
  }

  // ---- drag and drop -----------------------------------------------------------

  const hasFiles = (e: DragEvent) => e.dataTransfer.types.includes("Files");

  const dragProps = {
    onDragEnter: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepth.current += 1;
      setDragging(true);
    },
    onDragOver: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault(); // also stops the browser opening the file
      e.dataTransfer.dropEffect = canUpload ? "copy" : "none";
    },
    onDragLeave: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setDragging(false);
    },
    onDrop: (e: DragEvent<HTMLElement>) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      if (!canUpload) return;
      // A dropped folder arrives as a File too; its entry tells us it's a directory.
      const entries = Array.from(e.dataTransfer.items).filter((it) => it.kind === "file");
      const files = Array.from(e.dataTransfer.files).filter((_, i) => !entries[i]?.webkitGetAsEntry()?.isDirectory);
      if (files.length < e.dataTransfer.files.length) {
        toast({ tone: "info", title: "Folders were skipped", description: "Drop individual files to upload them." });
      }
      startUploads(files);
    },
  };

  // ---- render --------------------------------------------------------------------

  const title = prefix ? folderName(prefix) : "All files";
  const fileCount = rows.filter((r) => r.kind === "file").length;

  let body: ReactNode;
  if (!ready || !signedIn || (loading && !data)) {
    body = <TableSkeleton />;
  } else if (!hasRole) {
    body = (
      <EmptyState icon={<UserRoundX className="size-5" aria-hidden />} title="No access yet">
        Your account isn&apos;t assigned to a team or partner group. Ask an administrator to add you.
      </EmptyState>
    );
  } else if (error) {
    body =
      error.status === 403 ? (
        <EmptyState
          icon={<ShieldAlert className="size-5" aria-hidden />}
          title="You don't have access to this folder"
          action={<Link href={filesHref(sidebarFolders(groups)[0] ?? "")} className={buttonClass("secondary")}>Go to your files</Link>}
        >
          If you think you should, ask an administrator to update your role.
        </EmptyState>
      ) : (
        <EmptyState
          icon={<RefreshCw className="size-5" aria-hidden />}
          title="Couldn't load files"
          action={<Button onClick={() => void load()}>Try again</Button>}
        >
          {error.message}
        </EmptyState>
      );
  } else if (!rows.length) {
    body = filter ? (
      <EmptyState icon={<Search className="size-5" aria-hidden />} title="No matches">
        Nothing here matches &ldquo;{filter}&rdquo;.
      </EmptyState>
    ) : (
      <EmptyState
        icon={<FolderOpen className="size-5" aria-hidden />}
        title="This folder is empty"
        action={canUpload && <Button variant="primary" onClick={() => fileInput.current?.click()}><CloudUpload className="size-4" aria-hidden />Upload files</Button>}
      >
        {canUpload ? "Drag files here or use the upload button to publish the first artifact." : "Nothing has been published here yet."}
      </EmptyState>
    );
  } else {
    body = (
      <FileTable
        rows={rows}
        canRead={(key) => can(groups, "read", key)}
        canDelete={(key) => can(groups, "delete", key)}
        downloading={downloading}
        onDownload={(row) => void download(row)}
        onDelete={setPendingDelete}
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6 lg:flex-row lg:gap-8 lg:py-10">
      <Sidebar groups={groups} prefix={prefix} />

      <main className="relative min-w-0 flex-1" {...dragProps}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <Breadcrumb prefix={prefix} />
            <h1 className="mt-2 truncate text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted">
              {loading && !data ? "Loading…" : `${fileCount} file${fileCount === 1 ? "" : "s"}${canUpload ? " · you can publish here" : ""}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => void load()} aria-label="Refresh" disabled={loading}>
              <RefreshCw className={cx("size-4", loading && "animate-spin")} aria-hidden />
            </Button>
            {canUpload && (
              <Button variant="primary" onClick={() => fileInput.current?.click()}>
                <CloudUpload className="size-4" aria-hidden />
                Upload
              </Button>
            )}
            <input
              ref={fileInput}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                startUploads(Array.from(e.target.files ?? []));
                e.target.value = ""; // allow re-selecting the same file
              }}
            />
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-sm shadow-black/[0.03]">
          <div className="border-b border-border p-3">
            <label htmlFor="file-filter" className="sr-only">Filter files in this folder</label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
              <input
                id="file-filter"
                type="search"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter by name…"
                autoComplete="off"
                className="h-9 w-full rounded-lg border border-border bg-bg pl-9 pr-3 text-sm placeholder:text-subtle transition-colors hover:border-border-strong focus:border-accent focus:outline-none focus-visible:outline-none focus:ring-2 focus:ring-accent/30 sm:max-w-xs"
              />
            </div>
          </div>
          {body}
        </div>

        {data?.truncated && (
          <p className="mt-3 text-xs text-warning">
            Showing the first 1,000 objects. Open a subfolder or use the filter to narrow things down.
          </p>
        )}

        {ready && config && signedIn && hasRole && <ActivityPanel config={config} version={activityVersion} />}

        {dragging && (
          <div
            aria-hidden
            className={cx(
              "pointer-events-none absolute -inset-2 z-10 flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed backdrop-blur-sm",
              canUpload ? "border-accent bg-accent/10 text-accent" : "border-border-strong bg-bg/70 text-muted",
            )}
          >
            {canUpload ? <CloudUpload className="size-8" /> : <ShieldAlert className="size-8" />}
            <p className="text-sm font-medium">
              {canUpload ? `Drop to publish to ${prefix}` : "You can't upload to this folder"}
            </p>
          </div>
        )}
      </main>

      <UploadPanel uploads={uploads} onClear={() => setUploads((all) => all.filter((u) => u.status === "uploading"))} />

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Delete ${pendingDelete?.name ?? "file"}?`}
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      >
        <code className="break-all rounded bg-elevated px-1 py-0.5 font-mono text-xs text-fg">{pendingDelete?.key}</code>{" "}
        will be removed for everyone who can see this folder.
      </ConfirmDialog>
    </div>
  );
}
