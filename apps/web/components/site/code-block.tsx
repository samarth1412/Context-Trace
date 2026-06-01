import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function CodeBlock({
  children,
  language = "python",
  className
}: {
  children: ReactNode;
  language?: string;
  className?: string;
}) {
  return (
    <div className={cn("overflow-hidden rounded-lg border bg-slate-950 text-slate-100 shadow-sm", className)}>
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-slate-400">
        <span>{language}</span>
        <span>ContextTrace</span>
      </div>
      <pre className="overflow-x-auto p-4 text-sm leading-6">
        <code>{children}</code>
      </pre>
    </div>
  );
}

