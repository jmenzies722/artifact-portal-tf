"use client";

import { Download, File as FileIcon, FileArchive, FileCode, Folder, LoaderCircle, Package, Trash2 } from "lucide-react";
import Link from "next/link";
import { absoluteTime, cx, formatBytes, relativeTime } from "@/lib/format";
import { filesHref, type FileRow, type Row } from "@/lib/tree";

function fileIcon(name: string) {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (["zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "jar", "war"].includes(ext)) return FileArchive;
  if (["dmg", "pkg", "msi", "exe", "deb", "rpm", "apk", "ipa", "appimage"].includes(ext)) return Package;
  if (["json", "yaml", "yml", "toml", "xml", "sh", "py", "js", "ts"].includes(ext)) return FileCode;
  return FileIcon;
}

const iconButton =
  "flex size-8 items-center justify-center rounded-md text-subtle transition-colors disabled:opacity-50";

type Props = {
  rows: Row[];
  canRead: (key: string) => boolean;
  canDelete: (key: string) => boolean;
  downloading: string | null;
  onDownload: (row: FileRow) => void;
  onDelete: (row: FileRow) => void;
};

export function FileTable({ rows, canRead, canDelete, downloading, onDownload, onDelete }: Props) {
  return (
    <table className="w-full table-fixed text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-subtle">
          <th scope="col" className="px-4 py-2.5 font-medium">Name</th>
          <th scope="col" className="hidden w-28 px-4 py-2.5 text-right font-medium sm:table-cell">Size</th>
          <th scope="col" className="hidden w-40 px-4 py-2.5 font-medium md:table-cell">Modified</th>
          <th scope="col" className="w-24 px-4 py-2.5">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map((row) =>
          row.kind === "folder" ? (
            <tr key={row.prefix} className="group transition-colors hover:bg-elevated/50">
              <td className="px-4 py-2.5">
                <Link href={filesHref(row.prefix)} className="flex min-w-0 items-center gap-3 rounded-md font-medium">
                  <Folder className="size-4 shrink-0 fill-accent/15 text-accent" aria-hidden />
                  <span className="truncate group-hover:text-accent">{row.name}</span>
                </Link>
              </td>
              <td className="hidden px-4 py-2.5 text-right tabular-nums text-muted sm:table-cell">
                {row.count ? formatBytes(row.size) : "—"}
              </td>
              <td className="hidden px-4 py-2.5 text-muted md:table-cell">
                {row.modified ? <time dateTime={row.modified} title={absoluteTime(row.modified)}>{relativeTime(row.modified)}</time> : "—"}
              </td>
              <td className="px-4 py-2.5 text-right text-xs text-subtle">
                {row.count === 1 ? "1 item" : `${row.count} items`}
              </td>
            </tr>
          ) : (
            <FileRowView
              key={row.key}
              row={row}
              readable={canRead(row.key)}
              deletable={canDelete(row.key)}
              busy={downloading === row.key}
              onDownload={onDownload}
              onDelete={onDelete}
            />
          ),
        )}
      </tbody>
    </table>
  );
}

function FileRowView({
  row,
  readable,
  deletable,
  busy,
  onDownload,
  onDelete,
}: {
  row: FileRow;
  readable: boolean;
  deletable: boolean;
  busy: boolean;
  onDownload: (row: FileRow) => void;
  onDelete: (row: FileRow) => void;
}) {
  const Icon = fileIcon(row.name);
  return (
    <tr className="transition-colors hover:bg-elevated/50">
      <td className="px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <Icon className="size-4 shrink-0 text-subtle" aria-hidden />
          {readable ? (
            <button
              type="button"
              onClick={() => onDownload(row)}
              title={row.key}
              className="truncate rounded-md text-left hover:text-accent"
            >
              {row.name}
            </button>
          ) : (
            <span className="truncate" title={row.key}>{row.name}</span>
          )}
        </div>
      </td>
      <td className="hidden px-4 py-2.5 text-right tabular-nums text-muted sm:table-cell">{formatBytes(row.size)}</td>
      <td className="hidden px-4 py-2.5 text-muted md:table-cell">
        <time dateTime={row.modified} title={absoluteTime(row.modified)}>{relativeTime(row.modified)}</time>
      </td>
      <td className="px-3 py-1.5">
        <div className="flex justify-end gap-0.5">
          {readable && (
            <button
              type="button"
              className={cx(iconButton, "hover:bg-elevated hover:text-fg")}
              onClick={() => onDownload(row)}
              disabled={busy}
              aria-label={`Download ${row.name}`}
              title="Download"
            >
              {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <Download className="size-4" aria-hidden />}
            </button>
          )}
          {deletable && (
            <button
              type="button"
              className={cx(iconButton, "hover:bg-danger/10 hover:text-danger")}
              onClick={() => onDelete(row)}
              aria-label={`Delete ${row.name}`}
              title="Delete"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  const widths = ["w-48", "w-64", "w-40", "w-56", "w-36", "w-52"];
  return (
    <div role="status" aria-label="Loading files" className="divide-y divide-border">
      <div className="px-4 py-3">
        <div className="h-3 w-16 animate-pulse rounded bg-elevated" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3.5">
          <div className="size-4 animate-pulse rounded bg-elevated" />
          <div className={`h-3.5 ${widths[i % widths.length]} max-w-[50%] animate-pulse rounded bg-elevated`} />
          <div className="ml-auto hidden h-3.5 w-14 animate-pulse rounded bg-elevated sm:block" />
          <div className="hidden h-3.5 w-24 animate-pulse rounded bg-elevated md:block" />
        </div>
      ))}
    </div>
  );
}
