import { QueryConsole } from "@/components/playground/query-console";
import { StrategyComparison } from "@/components/playground/strategy-comparison";
import { SiteShell } from "@/components/site/site-shell";
import { ButtonLink } from "@/components/ui/button";

export default function PlaygroundPage() {
  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-6 max-w-3xl">
          <div className="text-sm font-semibold uppercase text-primary">Playground</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">
            Test RAG strategies and inspect the generated trace.
          </h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            Upload documents, run a query, compare retrieval strategies, and review citation
            verification results from the same trace format used by the SDK.
          </p>
        </header>
        <div className="mb-4">
          <ButtonLink href="/playground/upload">Upload Documents</ButtonLink>
        </div>
        <div className="grid gap-4">
          <QueryConsole />
          <StrategyComparison />
        </div>
      </main>
    </SiteShell>
  );
}
