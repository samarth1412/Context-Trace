import {
  ArrowRight,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  FileText,
  Github,
  Layers3,
  SearchCheck,
  ShieldAlert,
  SplitSquareHorizontal,
  Terminal,
  XCircle
} from "lucide-react";
import Link from "next/link";
import { CodeBlock } from "@/components/site/code-block";
import { SiteShell } from "@/components/site/site-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { quickstartSnippet, useCases } from "@/lib/site-content";

const problemItems = [
  "RAG systems fail silently.",
  "Citations often do not support answers.",
  "Retrievers miss critical evidence.",
  "Long context increases cost and noise.",
  "Agents use stale or irrelevant memory."
];

const evidenceItems = [
  "Retrieved chunks",
  "Selected context",
  "Dropped context",
  "Answer claims",
  "Citation verdicts",
  "Failure type",
  "Suggested fix",
  "Token/cost/latency"
];

const metrics = [
  { label: "Citation support", value: "91%", icon: SearchCheck },
  { label: "Unsupported claims", value: "6%", icon: ShieldAlert },
  { label: "Average latency", value: "636 ms", icon: Clock3 },
  { label: "Cost per trace", value: "$0.000251", icon: CircleDollarSign }
];

export default function HomePage() {
  return (
    <SiteShell>
      <main>
        <section className="relative overflow-hidden border-b bg-white">
          <HeroScene />
          <div className="relative mx-auto grid min-h-[calc(100vh-7.5rem)] max-w-7xl content-center px-4 py-16 md:px-7 lg:min-h-[680px]">
            <Badge tone="blue" className="mb-5 w-fit">
              RAG reliability SDK
            </Badge>
            <h1 className="max-w-4xl text-4xl font-semibold tracking-normal text-slate-950 md:text-6xl">
              Debug RAG failures before users find them.
            </h1>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600 md:text-xl">
              Trace retrieval, verify citations, classify failure modes, and generate reliability
              reports for RAG and agent applications.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/docs/quickstart"
                className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                Get Started
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                href="/traces/trace_refund_supported"
                className="inline-flex h-10 items-center rounded-md border bg-white px-4 text-sm font-semibold hover:bg-muted"
              >
                View Demo Trace
              </Link>
              <Link
                href="/benchmark"
                className="inline-flex h-10 items-center rounded-md border bg-white px-4 text-sm font-semibold hover:bg-muted"
              >
                Read Benchmark
              </Link>
              <Link
                href="https://github.com/samarth1412/Context-Trace"
                className="inline-flex h-10 items-center gap-2 rounded-md border bg-white px-4 text-sm font-semibold hover:bg-muted"
              >
                <Github className="h-4 w-4" aria-hidden="true" />
                GitHub
              </Link>
            </div>
          </div>
        </section>

        <section className="border-b">
          <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 md:px-7 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div className="text-sm font-semibold uppercase text-primary">Problem</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-normal text-foreground">
                RAG systems fail in ways ordinary traces do not explain.
              </h2>
              <p className="mt-4 text-base leading-7 text-muted-foreground">
                Logs tell you that a model answered. ContextTrace shows whether the answer had the
                right evidence, whether the citation supported the claim, and what to try next.
              </p>
            </div>
            <div className="grid gap-3">
              {problemItems.map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-lg border bg-card p-4">
                  <XCircle className="h-5 w-5 text-red-600" aria-hidden="true" />
                  <span className="font-medium">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b bg-white">
          <div className="mx-auto max-w-7xl px-4 py-14 md:px-7">
            <div className="mb-8 max-w-3xl">
              <div className="text-sm font-semibold uppercase text-primary">What ContextTrace shows</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-normal">
                Evidence-level debugging for every answer.
              </h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {evidenceItems.map((item) => (
                <Card key={item}>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                    <span className="font-medium">{item}</span>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b">
          <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 md:px-7 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div className="text-sm font-semibold uppercase text-primary">SDK quickstart</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-normal">Add tracing without rewriting your RAG app.</h2>
              <p className="mt-4 text-base leading-7 text-muted-foreground">
                The SDK wraps your existing retrieval and generation flow. Use hosted mode for a team
                backend or local mode for private traces and HTML reports.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Link
                  href="/docs/quickstart"
                  className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  Install SDK
                </Link>
                <Link
                  href="/playground"
                  className="inline-flex h-10 items-center rounded-md border bg-card px-4 text-sm font-semibold hover:bg-muted"
                >
                  Try Playground
                </Link>
              </div>
            </div>
            <CodeBlock>{quickstartSnippet}</CodeBlock>
          </div>
        </section>

        <section className="border-b bg-white">
          <div className="mx-auto max-w-7xl px-4 py-14 md:px-7">
            <div className="mb-8 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div>
                <div className="text-sm font-semibold uppercase text-primary">Dashboard</div>
                <h2 className="mt-2 text-3xl font-semibold tracking-normal">Screenshots and report previews.</h2>
              </div>
              <span className="text-sm text-muted-foreground">Placeholders until hosted screenshots are finalized.</span>
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              {["Trace detail", "Citation checks", "Failure report"].map((title, index) => (
                <div key={title} className="rounded-lg border bg-slate-50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-semibold">{title}</span>
                    <span className="text-xs text-muted-foreground">0{index + 1}</span>
                  </div>
                  <div className="space-y-2">
                    <div className="h-3 w-2/3 rounded-sm bg-slate-300" />
                    <div className="h-24 rounded-md border bg-white" />
                    <div className="grid grid-cols-3 gap-2">
                      <div className="h-10 rounded-md bg-white" />
                      <div className="h-10 rounded-md bg-white" />
                      <div className="h-10 rounded-md bg-white" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b">
          <div className="mx-auto max-w-7xl px-4 py-14 md:px-7">
            <div className="mb-8 max-w-3xl">
              <div className="text-sm font-semibold uppercase text-primary">Use cases</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-normal">Built for teams shipping evidence-backed LLM apps.</h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {useCases.map((useCase) => (
                <Card key={useCase}>
                  <CardHeader>
                    <CardTitle>{useCase}</CardTitle>
                  </CardHeader>
                  <p className="text-sm leading-6 text-muted-foreground">
                    Trace evidence, diagnose failures, and compare retrieval strategies before users
                    see unsupported answers.
                  </p>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white">
          <div className="mx-auto grid max-w-7xl gap-6 px-4 py-14 md:px-7 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <h2 className="text-3xl font-semibold tracking-normal">Start with one trace.</h2>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                Install the SDK, run a local report, or open the playground to inspect a complete
                trace lifecycle.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/docs/quickstart"
                className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                Install SDK
              </Link>
              <Link
                href="/playground"
                className="inline-flex h-10 items-center rounded-md border bg-card px-4 text-sm font-semibold hover:bg-muted"
              >
                Try Playground
              </Link>
              <Link
                href="https://github.com/samarth1412/Context-Trace"
                className="inline-flex h-10 items-center rounded-md border bg-card px-4 text-sm font-semibold hover:bg-muted"
              >
                Star on GitHub
              </Link>
            </div>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}

function HeroScene() {
  return (
    <div className="pointer-events-none absolute inset-0 opacity-75" aria-hidden="true">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#e5e7eb_1px,transparent_1px),linear-gradient(to_bottom,#e5e7eb_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="absolute right-[-120px] top-12 hidden w-[680px] rounded-lg border bg-white/90 p-4 shadow-sm lg:block">
        <div className="mb-4 flex items-center justify-between border-b pb-3">
          <span className="text-sm font-semibold">Trace timeline</span>
          <span className="rounded-sm bg-emerald-50 px-2 py-1 text-xs text-emerald-700">evaluated</span>
        </div>
        <div className="grid gap-3">
          <HeroRow icon={Layers3} title="Retrieved chunks" detail="8 candidate passages" />
          <HeroRow icon={SplitSquareHorizontal} title="Selected context" detail="5 chunks, 3 dropped" />
          <HeroRow icon={FileText} title="Citation verdicts" detail="4 supported, 1 partial" />
          <HeroRow icon={Terminal} title="Suggested fix" detail="Add sentence-level citation verification" />
        </div>
        <div className="mt-4 grid grid-cols-4 gap-2">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-md border bg-slate-50 p-3">
              <metric.icon className="mb-2 h-4 w-4 text-primary" aria-hidden="true" />
              <div className="text-sm font-semibold">{metric.value}</div>
              <div className="text-xs text-muted-foreground">{metric.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HeroRow({
  icon: Icon,
  title,
  detail
}: {
  icon: typeof Layers3;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border bg-white p-3">
      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      <div>
        <div className="text-sm font-medium">{title}</div>
        <div className="text-xs text-muted-foreground">{detail}</div>
      </div>
    </div>
  );
}

