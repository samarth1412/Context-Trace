import { FileCode2 } from "lucide-react";
import Link from "next/link";
import { CodeBlock } from "@/components/site/code-block";
import { SiteShell } from "@/components/site/site-shell";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

const examples = [
  ["custom_rag.py", "Trace a hand-rolled retriever and LLM generation flow."],
  ["langchain_rag.py", "Capture LangChain inputs, retrieved documents, output, and latency."],
  ["llamaindex_rag.py", "Capture LlamaIndex retrieved nodes, source nodes, and response metadata."],
  ["agent_trace.py", "Log planner, tool, memory, and error events in one trace timeline."],
  ["local_report.py", "Create a local HTML report without a hosted backend."],
  ["batch_eval.py", "Create eval sets and aggregate reliability metrics."]
];

export default function ExamplesPage() {
  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-8 max-w-3xl">
          <div className="text-sm font-semibold uppercase text-primary">Examples</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">Trace real RAG and agent workflows.</h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            Start from a minimal custom RAG script, then add framework integrations, local reports,
            batch evals, and agent timelines.
          </p>
        </header>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {examples.map(([name, description]) => (
            <Card key={name}>
              <CardHeader>
                <CardTitle>
                  <span className="flex items-center gap-2">
                    <FileCode2 className="h-4 w-4 text-primary" aria-hidden="true" />
                    {name}
                  </span>
                </CardTitle>
              </CardHeader>
              <p className="text-sm leading-6 text-muted-foreground">{description}</p>
            </Card>
          ))}
        </div>
        <section className="mt-8 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <CardTitle>Run locally</CardTitle>
            </CardHeader>
            <p className="text-sm leading-6 text-muted-foreground">
              Examples live in the repository under `examples/`. They are written to keep your RAG
              implementation responsible for retrieval and generation while ContextTrace records the
              evidence lifecycle.
            </p>
            <Link
              href="/docs/quickstart"
              className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            >
              Read quickstart
            </Link>
          </Card>
          <CodeBlock language="bash">{`python examples/custom_rag.py
python examples/local_report.py
python examples/batch_eval.py`}</CodeBlock>
        </section>
      </main>
    </SiteShell>
  );
}

