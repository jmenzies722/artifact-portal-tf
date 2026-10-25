import { Compass } from "lucide-react";
import Link from "next/link";
import { buttonClass } from "@/components/ui";

export default function NotFound() {
  return (
    <main className="flex min-h-[calc(100dvh-3.5rem)] flex-col items-center justify-center px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl border border-border bg-elevated text-muted">
        <Compass className="size-5" aria-hidden />
      </div>
      <p className="mt-6 font-mono text-sm text-accent">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">This page doesn&apos;t exist</h1>
      <p className="mt-2 max-w-sm text-sm text-muted">
        The link may be broken or the page may have moved.
      </p>
      <Link href="/" className={buttonClass("primary", "md", "mt-8")}>
        Back to home
      </Link>
    </main>
  );
}
