import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { DocsLayout } from "@/components/site/docs-layout";
import { CodeBlock } from "@/components/site/code-block";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { docsNav, quickstartSnippet } from "@/lib/site-content";

export default function DocsIndexPage() {
  return (
    <DocsLayout
      title="ContextTrace Docs"
      description="Use ContextTrace as an SDK-first reliability layer for RAG and agent applications."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {docsNav.slice(1).map((item) => (
          <Link key={item.href} href={item.href} className="block">
            <Card className="h-full hover:bg-muted">
              <CardHeader>
                <CardTitle>{item.label}</CardTitle>
              </CardHeader>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                Read documentation
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </div>
            </Card>
          </Link>
        ))}
      </div>
      <section>
        <h2 className="mb-3 text-xl font-semibold tracking-normal">Copy-paste quickstart</h2>
        <CodeBlock>{quickstartSnippet}</CodeBlock>
      </section>
    </DocsLayout>
  );
}

