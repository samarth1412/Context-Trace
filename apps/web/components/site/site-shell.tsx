import type { ReactNode } from "react";
import { BookOpen, Github, LayoutDashboard, ListChecks, Play, Terminal } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/docs", label: "Docs" },
  { href: "/examples", label: "Examples" },
  { href: "/playground", label: "Playground" },
  { href: "/benchmark", label: "Benchmark" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" }
];

export function SiteShell({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("min-h-screen bg-background", className)}>
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 md:px-7">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ListChecks className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="text-sm font-semibold">ContextTrace</span>
          </Link>
          <nav className="hidden items-center gap-5 text-sm text-muted-foreground lg:flex">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="hover:text-foreground">
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard"
              className="hidden h-9 items-center gap-2 rounded-md border bg-card px-3 text-sm font-medium hover:bg-muted sm:inline-flex"
            >
              <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
              Dashboard
            </Link>
            <Link
              href="https://github.com/samarth1412/Context-Trace"
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Github className="h-4 w-4" aria-hidden="true" />
              GitHub
            </Link>
          </div>
        </div>
      </header>
      {children}
      <footer className="border-t bg-card">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 text-sm text-muted-foreground md:grid-cols-[1.3fr_1fr_1fr] md:px-7">
          <div>
            <div className="mb-2 flex items-center gap-2 text-foreground">
              <ListChecks className="h-4 w-4" aria-hidden="true" />
              <span className="font-semibold">ContextTrace</span>
            </div>
            <p className="max-w-md">
              Evidence-level tracing, citation verification, and failure diagnosis for RAG and agent
              applications.
            </p>
          </div>
          <div className="grid gap-2">
            <Link href="/docs/quickstart" className="inline-flex items-center gap-2 hover:text-foreground">
              <BookOpen className="h-4 w-4" aria-hidden="true" />
              Quickstart
            </Link>
            <Link href="/examples" className="inline-flex items-center gap-2 hover:text-foreground">
              <Terminal className="h-4 w-4" aria-hidden="true" />
              Examples
            </Link>
          </div>
          <div className="grid gap-2">
            <Link href="/playground" className="inline-flex items-center gap-2 hover:text-foreground">
              <Play className="h-4 w-4" aria-hidden="true" />
              Playground
            </Link>
            <Link href="/benchmark" className="hover:text-foreground">
              Public benchmark
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

