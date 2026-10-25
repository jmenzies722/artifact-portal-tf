"use client";

import { LogIn, LogOut, Moon, Package, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "@/lib/format";
import { knownRoles } from "@/lib/rbac";
import { usePortal } from "./providers";
import { Button, RoleBadge } from "./ui";

function ThemeToggle() {
  // Icons swap via the `dark` class, so there's no hydration flash or state.
  const toggle = () => {
    const dark = document.documentElement.classList.toggle("dark");
    try {
      localStorage.setItem("ap.theme", dark ? "dark" : "light");
    } catch {
      /* private mode: preference just isn't remembered */
    }
  };
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle color theme"
      className="flex size-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-elevated hover:text-fg"
    >
      <Sun className="hidden size-4 dark:block" aria-hidden />
      <Moon className="size-4 dark:hidden" aria-hidden />
    </button>
  );
}

function NavLink({ href, children }: { href: string; children: string }) {
  const active = usePathname()?.startsWith(href);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cx(
        "rounded-md px-2.5 py-1.5 text-sm transition-colors",
        active ? "bg-elevated text-fg" : "text-muted hover:text-fg",
      )}
    >
      {children}
    </Link>
  );
}

export function SiteHeader() {
  const { ready, config, user, signIn, signOut } = usePortal();
  const roles = user ? knownRoles(user.groups) : [];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href={user ? "/files/" : "/"} className="flex items-center gap-2.5 rounded-md font-semibold tracking-tight">
          <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-accent-fg shadow-sm shadow-accent/30">
            <Package className="size-4" aria-hidden />
          </span>
          <span className="hidden sm:inline">Artifact Portal</span>
        </Link>

        <nav aria-label="Main" className="flex items-center gap-1">
          {user && <NavLink href="/files/">Files</NavLink>}
          <NavLink href="/about/">About</NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {!ready ? (
            <div className="h-8 w-24 animate-pulse rounded-lg bg-elevated" aria-hidden />
          ) : user ? (
            <>
              <div className="hidden items-center gap-2 md:flex">
                <span className="max-w-[16rem] truncate text-sm text-muted" title={user.email}>
                  {user.email}
                </span>
                {roles.map((r) => (
                  <RoleBadge key={r} group={r} />
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={signOut} aria-label="Sign out">
                <LogOut className="size-4" aria-hidden />
                <span className="hidden sm:inline">Sign out</span>
              </Button>
            </>
          ) : (
            <Button variant="primary" size="sm" onClick={signIn} disabled={!config}>
              <LogIn className="size-4" aria-hidden />
              Sign in
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
