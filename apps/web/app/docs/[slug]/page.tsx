import { notFound } from "next/navigation";
import { CodeBlock } from "@/components/site/code-block";
import { DocsLayout } from "@/components/site/docs-layout";
import { docsPages } from "@/lib/site-content";

type DocsSlug = keyof typeof docsPages;

export function generateStaticParams() {
  return Object.keys(docsPages).map((slug) => ({ slug }));
}

export default async function DocsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const page = docsPages[slug as DocsSlug];
  if (!page) {
    notFound();
  }

  return (
    <DocsLayout title={page.title} description={page.description}>
      {page.sections.map((section) => (
        <section key={section.title} className="rounded-lg border bg-card p-5">
          <h2 className="text-xl font-semibold tracking-normal">{section.title}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{section.body}</p>
          {"code" in section && section.code ? (
            <CodeBlock className="mt-4" language={section.code.includes("POST /") ? "http" : "python"}>
              {section.code}
            </CodeBlock>
          ) : null}
        </section>
      ))}
    </DocsLayout>
  );
}

