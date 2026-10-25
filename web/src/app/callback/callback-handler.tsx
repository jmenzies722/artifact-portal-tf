"use client";

import { CircleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { usePortal } from "@/components/providers";
import { Button, buttonClass, Spinner } from "@/components/ui";
import { completeSignIn } from "@/lib/auth";

export function CallbackHandler() {
  const { config, configError, signIn } = usePortal();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!config) return;
    completeSignIn(config, new URLSearchParams(window.location.search))
      .then(() => router.replace("/files/"))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, [config, router]);

  const message = error ?? configError;
  if (!message) return <Spinner label="Signing you in…" />;

  return (
    <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 text-center shadow-xl shadow-black/5">
      <div className="mx-auto flex size-11 items-center justify-center rounded-full bg-danger/10 text-danger">
        <CircleAlert className="size-5" aria-hidden />
      </div>
      <h1 className="mt-4 text-lg font-semibold">Sign-in didn&apos;t complete</h1>
      <p role="alert" className="mt-2 text-sm text-muted">
        {message}
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/" className={buttonClass("secondary")}>
          Home
        </Link>
        <Button variant="primary" onClick={signIn} disabled={!config}>
          Try again
        </Button>
      </div>
    </div>
  );
}
