"use client";

import { Code, Folder, Globe, Handshake, Layers, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { cx, folderName } from "@/lib/format";
import { can, knownRoles, ROLE_LABELS, sidebarFolders } from "@/lib/rbac";
import { filesHref } from "@/lib/tree";
import { RoleBadge } from "../ui";

const META: Record<string, { icon: LucideIcon; label: string }> = {
  "public/": { icon: Globe, label: "Public" },
  "partners/": { icon: Handshake, label: "Partners" },
  "develop/": { icon: Code, label: "Develop" },
};

function folderMeta(prefix: string) {
  if (META[prefix]) return META[prefix];
  const name = folderName(prefix);
  return {
    icon: prefix.startsWith("partners/") ? Handshake : Folder,
    label: ROLE_LABELS[name] ?? name,
  };
}

type Entry = { prefix: string; icon: LucideIcon; label: string };

export function Sidebar({ groups, prefix }: { groups: string[]; prefix: string }) {
  const folders = sidebarFolders(groups);
  const entries: Entry[] = [
    { prefix: "", icon: Layers, label: "All files" },
    ...folders.map((p) => ({ prefix: p, ...folderMeta(p) })),
  ];
  const isActive = (p: string) => (p ? prefix.startsWith(p) : prefix === "");
  const roles = knownRoles(groups);

  return (
    <>
      {/* Mobile: horizontal chips */}
      <nav aria-label="Folders" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:-mx-6 sm:px-6 lg:hidden">
        {entries.map(({ prefix: p, icon: Icon, label }) => (
          <Link
            key={p || "root"}
            href={filesHref(p)}
            aria-current={isActive(p) ? "page" : undefined}
            className={cx(
              "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
              isActive(p)
                ? "border-accent/30 bg-accent/10 text-accent"
                : "border-border bg-surface text-muted hover:text-fg",
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>

      {/* Desktop: sidebar */}
      <aside className="hidden w-60 shrink-0 lg:block">
        <div className="sticky top-20 space-y-6">
          <nav aria-label="Folders">
            <p className="px-2.5 pb-2 text-xs font-medium uppercase tracking-wide text-subtle">Folders</p>
            <ul className="space-y-0.5">
              {entries.map(({ prefix: p, icon: Icon, label }) => (
                <li key={p || "root"}>
                  <Link
                    href={filesHref(p)}
                    aria-current={isActive(p) ? "page" : undefined}
                    className={cx(
                      "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                      isActive(p) ? "bg-elevated font-medium text-fg" : "text-muted hover:bg-elevated/60 hover:text-fg",
                    )}
                  >
                    <Icon className={cx("size-4", isActive(p) ? "text-accent" : "text-subtle")} aria-hidden />
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <section aria-label="Your access" className="rounded-xl border border-border bg-surface p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-subtle">Your access</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {roles.length ? roles.map((r) => <RoleBadge key={r} group={r} />) : (
                <span className="text-sm text-muted">No role assigned</span>
              )}
            </div>
            {folders.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm">
                {folders.map((p) => (
                  <li key={p} className="flex items-center justify-between gap-2">
                    <span className="truncate text-muted">{folderMeta(p).label}</span>
                    <span className="shrink-0 text-xs text-subtle">
                      {can(groups, "write", p) ? "Read & write" : "Read only"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
