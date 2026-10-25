import type { Metadata } from "next";
import { CallbackHandler } from "./callback-handler";

export const metadata: Metadata = { title: "Signing in" };

export default function CallbackPage() {
  return (
    <main className="flex min-h-[calc(100dvh-3.5rem)] items-center justify-center px-6">
      <CallbackHandler />
    </main>
  );
}
