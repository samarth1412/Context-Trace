import { AlertTriangle, CheckCircle2, Clock, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AgentTimeline({ events }: { events: AgentEvent[] }) {
  const ordered = [...events].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Timeline</CardTitle>
      </CardHeader>
      {ordered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No agent events logged.</p>
      ) : (
        <ol className="grid gap-3">
          {ordered.map((event) => (
            <li
              key={event.id}
              className={cn(
                "rounded-md border p-3",
                event.error_message ? "border-destructive/40 bg-destructive/10" : "bg-card"
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                {event.error_message ? (
                  <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden="true" />
                ) : event.event_type === "tool_call" || event.event_type === "tool_result" ? (
                  <Wrench className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                )}
                <Badge tone={event.error_message ? "red" : "neutral"}>{event.event_type}</Badge>
                <span className="text-sm font-medium">{event.name ?? "unnamed event"}</span>
                {typeof event.latency_ms === "number" ? (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" aria-hidden="true" />
                    {Math.round(event.latency_ms)} ms
                  </span>
                ) : null}
              </div>

              {event.error_message ? (
                <p className="mt-2 text-sm text-destructive">{event.error_message}</p>
              ) : null}

              <div className="mt-3 grid gap-2 md:grid-cols-3">
                <PayloadBlock title="Input" value={event.input_json} />
                <PayloadBlock title="Output" value={event.output_json} />
                <PayloadBlock title="Metadata" value={event.metadata_json} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function PayloadBlock({ title, value }: { title: string; value: unknown }) {
  const text = JSON.stringify(value ?? {}, null, 2);
  return (
    <details className="rounded-md border bg-background p-2 text-xs">
      <summary className="cursor-pointer font-medium text-muted-foreground">{title}</summary>
      <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-5">
        {text}
      </pre>
    </details>
  );
}
