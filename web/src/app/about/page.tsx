import { ArrowDown, Cloud, Cpu, Database, KeyRound, Network, type LucideIcon } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "About" };

const LAYERS: { icon: LucideIcon; name: string; role: string; detail: string }[] = [
  {
    icon: Cloud,
    name: "Amazon CloudFront",
    role: "Edge & delivery",
    detail:
      "Serves this static site from a private S3 bucket through Origin Access Control, and routes /api/* to API Gateway under the same origin.",
  },
  {
    icon: KeyRound,
    name: "Amazon Cognito",
    role: "Identity",
    detail:
      "Hosted sign-in with authorization code + PKCE. Users belong to groups (developers, operations, testers, partners) that decide what they can see.",
  },
  {
    icon: Network,
    name: "Amazon API Gateway",
    role: "API front door",
    detail:
      "HTTP API with a Cognito JWT authorizer, throttling and access logs. Requests without a valid token never reach application code.",
  },
  {
    icon: Cpu,
    name: "AWS Lambda",
    role: "Business logic",
    detail:
      "Four small functions (list, upload, download, delete), each with least-privilege IAM. They re-check group permissions on every call and issue short-lived presigned URLs.",
  },
  {
    icon: Database,
    name: "Amazon S3 + AWS KMS",
    role: "Storage",
    detail:
      "Versioned artifact bucket encrypted with a customer-managed KMS key. Uploads use conditional writes, so a published version can never be overwritten.",
  },
];

const PRINCIPLES = [
  "Files move directly between your browser and S3 via presigned URLs. The API never proxies bytes.",
  "This interface hides what you can't use, but the API is the source of truth for every permission.",
  "Tokens are kept in memory and session storage only, and are cleared when you sign out or close the tab.",
  "Every API request is audit-logged with who, what, when and the access decision.",
];

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 sm:py-20">
      <p className="text-sm font-medium text-accent">Architecture</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">How the portal works</h1>
      <p className="mt-4 text-muted">
        A fully serverless stack on AWS, defined in Terraform. Each request flows through these layers, top to
        bottom.
      </p>

      <ol className="mt-12">
        {LAYERS.map(({ icon: Icon, name, role, detail }, i) => (
          <li key={name}>
            <div className="flex gap-4 rounded-2xl border border-border bg-surface p-5 transition-colors hover:border-border-strong">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-accent/20 bg-accent/10 text-accent">
                <Icon className="size-5" aria-hidden />
              </div>
              <div>
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <h2 className="font-semibold">{name}</h2>
                  <span className="text-xs uppercase tracking-wide text-subtle">{role}</span>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{detail}</p>
              </div>
            </div>
            {i < LAYERS.length - 1 && (
              <div className="flex justify-center py-2 text-subtle" aria-hidden>
                <ArrowDown className="size-4" />
              </div>
            )}
          </li>
        ))}
      </ol>

      <section className="mt-16">
        <h2 className="text-lg font-semibold">Security model</h2>
        <ul className="mt-4 space-y-3">
          {PRINCIPLES.map((p) => (
            <li key={p} className="flex gap-3 text-sm text-muted">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
              {p}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
