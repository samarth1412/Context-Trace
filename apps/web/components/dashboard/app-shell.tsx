import type { ReactNode } from "react";
import { Activity, BarChart3, FileText, LayoutDashboard, ListChecks, Plug, Search } from "lucide-react";
import Link from "next/link";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/traces", label: "Traces", icon: Activity },
  { href: "/playground", label: "Playground", icon: Search },
  { href: "/rag-api", label: "RAG APIs", icon: Plug },
  { href: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
  { href: "/reports", label: "Reports", icon: FileText }
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-card px-4 py-5 md:block">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ListChecks className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-semibold">ContextTrace</div>
            <div className="text-xs text-muted-foreground">RAG reliability</div>
          </div>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="mx-auto max-w-7xl px-4 py-5 md:ml-64 md:px-7">{children}</main>
    </div>
  );
}
