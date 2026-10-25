// GET /files returns every key under the prefix (no delimiter), so the
// folder view is derived here: one level below the current prefix.

import type { FileItem } from "./api";

export type FolderRow = {
  kind: "folder";
  name: string;
  prefix: string;
  count: number;
  size: number;
  modified: string | null;
};

export type FileRow = { kind: "file"; name: string; key: string; size: number; modified: string };

export type Row = FolderRow | FileRow;

const byName = (a: Row, b: Row) => a.name.localeCompare(b.name, undefined, { numeric: true });

/**
 * @param granted  prefixes the user may list; ones below `prefix` appear as
 *                 folders even when they hold no objects yet.
 */
export function buildRows(items: FileItem[], prefix: string, granted: string[]): Row[] {
  const folders = new Map<string, FolderRow>();
  const files: FileRow[] = [];

  const folder = (name: string): FolderRow => {
    let row = folders.get(name);
    if (!row) {
      row = { kind: "folder", name, prefix: `${prefix}${name}/`, count: 0, size: 0, modified: null };
      folders.set(name, row);
    }
    return row;
  };

  for (const g of granted) {
    if (g.length > prefix.length && g.startsWith(prefix)) folder(g.slice(prefix.length).split("/")[0]);
  }

  for (const item of items) {
    if (!item.key.startsWith(prefix)) continue;
    const rest = item.key.slice(prefix.length);
    const slash = rest.indexOf("/");
    if (slash === -1) {
      if (rest) files.push({ kind: "file", name: rest, key: item.key, size: item.size, modified: item.last_modified });
      continue;
    }
    const row = folder(rest.slice(0, slash));
    if (rest.length > slash + 1) {
      row.count += 1;
      row.size += item.size;
      // Same ISO-8601 format from the API, so string order is time order.
      if (!row.modified || item.last_modified > row.modified) row.modified = item.last_modified;
    }
  }

  return [...[...folders.values()].sort(byName), ...files.sort(byName)];
}

export function normalizePrefix(raw: string | null): string {
  const p = (raw ?? "").replace(/^\/+/, "");
  return p && !p.endsWith("/") ? `${p}/` : p;
}

export function filesHref(prefix: string): string {
  return prefix ? `/files/?prefix=${encodeURIComponent(prefix)}` : "/files/";
}
