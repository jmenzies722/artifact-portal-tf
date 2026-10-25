import { Lock, ShieldCheck, UsersRound } from "lucide-react";
import type { ReactNode } from "react";
import { HeroActions } from "./hero-actions";

const FEATURES: { icon: ReactNode; title: string; body: string }[] = [
  {
    icon: <ShieldCheck className="size-5" aria-hidden />,
    title: "Secure by default",
    body: "Single sign-on with Cognito, short-lived download links, and every artifact encrypted at rest with a customer-managed KMS key.",
  },
  {
    icon: <Lock className="size-5" aria-hidden />,
    title: "Immutable releases",
    body: "Once a version is published it can't be overwritten. What your customers download is exactly what you shipped.",
  },
  {
    icon: <UsersRound className="size-5" aria-hidden />,
    title: "Role-based access",
    body: "Developers, operations, testers and each partner see only their own folders, enforced server-side on every request.",
  },
];

export default function Home() {
  return (
    <main className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-40 mx-auto h-[32rem] max-w-4xl rounded-full bg-accent/20 blur-3xl dark:bg-accent/15"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:48px_48px] opacity-40 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
      />

      <section className="relative mx-auto max-w-3xl px-6 pb-20 pt-24 text-center sm:pt-32">
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted backdrop-blur">
          <span className="size-1.5 rounded-full bg-success" aria-hidden />
          Software distribution, done properly
        </span>
        <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-6xl">Artifact Portal</h1>
        <p className="mx-auto mt-5 max-w-xl text-base text-muted sm:text-lg">
          One secure place to publish builds and hand them to customers, partners and internal teams,
          with the right people seeing the right releases.
        </p>
        <HeroActions />
      </section>

      <section aria-label="Features" className="relative mx-auto grid max-w-5xl gap-4 px-6 pb-28 sm:grid-cols-3">
        {FEATURES.map((f) => (
          <article
            key={f.title}
            className="group rounded-2xl border border-border bg-surface/80 p-6 backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-xl hover:shadow-black/5"
          >
            <div className="flex size-10 items-center justify-center rounded-xl border border-accent/20 bg-accent/10 text-accent transition-colors group-hover:bg-accent/15">
              {f.icon}
            </div>
            <h2 className="mt-5 text-[15px] font-semibold">{f.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
