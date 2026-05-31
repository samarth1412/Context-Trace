import { Badge } from "@/components/ui/badge";
import type { DataSource } from "@/lib/types";

export function PageHeader({
  title,
  description,
  source,
  error
}: {
  title: string;
  description: string;
  source?: DataSource;
  error?: string;
}) {
  return (
    <header className="mb-5 flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
      </div>
      {source ? (
        <div className="flex items-center gap-2">
          <Badge tone={source === "backend" ? "green" : "amber"}>{source}</Badge>
          {error ? <span className="max-w-md truncate text-xs text-muted-foreground">{error}</span> : null}
        </div>
      ) : null}
    </header>
  );
}
