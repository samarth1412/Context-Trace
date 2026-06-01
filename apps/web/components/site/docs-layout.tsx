import type { ReactNode } from "react";
import Link from "next/link";
import { SiteShell } from "@/components/site/site-shell";
import { docsNav } from "@/lib/site-content";

export function DocsLayout({
  title,
  description,
  children
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <SiteShell>
      <main className="mx-auto grid max-w-7xl gap-8 px-4 py-8 md:grid-cols-[240px_1fr] md:px-7">
        <aside className="md:sticky md:top-20 md:h-[calc(100vh-6rem)]">
          <div className="rounded-lg border bg-card p-3">
            <div className="mb-2 px-2 text-xs font-semibold uppercase text-muted-foreground">Documentation</div>
            <nav className="grid gap-1">
              {docsNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </aside>
        <article className="min-w-0">
          <header className="mb-8 border-b pb-5">
            <h1 className="text-3xl font-semibold tracking-normal text-foreground md:text-4xl">{title}</h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-muted-foreground">{description}</p>
          </header>
          <div className="space-y-8">{children}</div>
        </article>
      </main>
    </SiteShell>
  );
}

