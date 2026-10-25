"use client";

import { ArrowRight, LogIn } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { usePortal } from "@/components/providers";
import { Button, buttonClass } from "@/components/ui";

export function HeroActions() {
  const { ready, config, configError, user, signIn } = usePortal();
  const router = useRouter();

  useEffect(() => {
    if (user) router.replace("/files/");
  }, [user, router]);

  return (
    <div className="mt-9 flex flex-col items-center gap-4">
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button variant="primary" size="lg" onClick={signIn} disabled={!config} loading={!ready}>
          {ready && <LogIn className="size-4" aria-hidden />}
          Sign in
        </Button>
        <Link href="/about/" className={buttonClass("secondary", "lg")}>
          How it works
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
      {configError && (
        <p role="alert" className="text-sm text-danger">
          The portal isn&apos;t configured yet: {configError}
        </p>
      )}
    </div>
  );
}
