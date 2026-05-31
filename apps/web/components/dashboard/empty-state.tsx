import { AlertTriangle } from "lucide-react";

export function EmptyState({
  title,
  detail
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-6 text-sm">
      <div className="mb-2 flex items-center gap-2 font-medium">
        <AlertTriangle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        {title}
      </div>
      <p className="text-muted-foreground">{detail}</p>
    </div>
  );
}
