import Link from "next/link";
import { SiteShell } from "@/components/site/site-shell";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

const posts = [
  {
    title: "Why citation support needs claim-level checks",
    description: "A RAG answer can cite the right document and still make an unsupported claim.",
    href: "/docs/api"
  },
  {
    title: "Benchmarking RAG strategies without hiding tradeoffs",
    description: "How ContextTrace reports support, failure rate, latency, tokens, and cost side by side.",
    href: "/benchmark"
  },
  {
    title: "Tracing agent memory and tools with the same evidence model",
    description: "Agent timelines add planner, tool, memory, and error events to RAG traces.",
    href: "/traces/trace_refund_supported"
  }
];

export default function BlogPage() {
  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-8 max-w-3xl">
          <div className="text-sm font-semibold uppercase text-primary">Blog</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">Notes on RAG reliability.</h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            Product notes, engineering writeups, and benchmark reports for teams building
            evidence-backed LLM systems.
          </p>
        </header>
        <div className="grid gap-4 md:grid-cols-3">
          {posts.map((post) => (
            <Link key={post.title} href={post.href} className="block">
              <Card className="h-full hover:bg-muted">
                <CardHeader>
                  <CardTitle>{post.title}</CardTitle>
                </CardHeader>
                <p className="text-sm leading-6 text-muted-foreground">{post.description}</p>
              </Card>
            </Link>
          ))}
        </div>
      </main>
    </SiteShell>
  );
}
