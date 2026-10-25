// UI mirror of lambda/shared/permissions.py GROUP_RULES. It only decides
// what to show; the API re-checks every request server-side.

export type Action = "list" | "read" | "write" | "delete";

const ALL: Action[] = ["list", "read", "write", "delete"];
const all = (prefixes: string[]) =>
  Object.fromEntries(ALL.map((a) => [a, prefixes])) as Record<Action, string[]>;

const GROUP_RULES: Record<string, Partial<Record<Action, string[]>>> = {
  developers: all(["public/", "partners/", "develop/"]),
  operations: all(["public/", "partners/"]),
  testers: { list: ["public/", "partners/"], read: ["public/", "partners/"] },
  partner_a: {
    list: ["public/", "partners/partner_a/"],
    read: ["public/", "partners/partner_a/"],
    write: ["partners/partner_a/"],
  },
  partner_b: {
    list: ["public/", "partners/partner_b/"],
    read: ["public/", "partners/partner_b/"],
    write: ["partners/partner_b/"],
  },
};

export const ROLE_LABELS: Record<string, string> = {
  developers: "Developer",
  operations: "Operations",
  testers: "Tester",
  partner_a: "Partner A",
  partner_b: "Partner B",
};

export function prefixesFor(groups: string[], action: Action): string[] {
  const out = new Set<string>();
  for (const g of groups) for (const p of GROUP_RULES[g]?.[action] ?? []) out.add(p);
  return [...out].sort();
}

export function can(groups: string[], action: Action, key: string): boolean {
  return prefixesFor(groups, action).some((p) => key.startsWith(p));
}

/** Top-level folders for the sidebar, with nested grants folded into their parent. */
export function sidebarFolders(groups: string[]): string[] {
  const list = prefixesFor(groups, "list");
  return list.filter((p) => !list.some((q) => q !== p && p.startsWith(q)));
}

export function knownRoles(groups: string[]): string[] {
  return groups.filter((g) => g in GROUP_RULES);
}
