import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { ContextPolicyMetadata } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

export function PolicyCard({ policy }: { policy?: ContextPolicyMetadata | null }) {
  if (!policy) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Context Policy</CardTitle>
        </CardHeader>
        <p className="text-sm text-muted-foreground">No context policy metadata logged.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Context Policy</CardTitle>
        <Badge tone={policy.selected_policy === "abstain_low_confidence" ? "amber" : "blue"}>
          {policy.selected_policy ?? "unknown"}
        </Badge>
      </CardHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Query Class</div>
          <div className="mt-1 text-sm font-medium">{policy.query_class ?? "unknown"}</div>
          {policy.query_class_reason ? (
            <p className="mt-1 text-sm text-muted-foreground">{policy.query_class_reason}</p>
          ) : null}
        </div>
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Retrieval</div>
          <div className="mt-1 text-sm font-medium">{policy.retrieval_strategy ?? "none"}</div>
          <p className="mt-1 text-sm text-muted-foreground">
            confidence {formatPercent(policy.retrieval_confidence ?? 0)}
          </p>
        </div>
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Token Budget</div>
          <div className="mt-1 text-sm font-medium">{policy.token_budget ?? 0}</div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Reason</div>
          <p className="mt-1 text-sm">{policy.reason ?? "No policy reason logged."}</p>
        </div>
        <ChunkIdList title="Selected Chunks" ids={policy.selected_chunk_ids ?? []} />
        <ChunkIdList title="Dropped Chunks" ids={policy.dropped_chunk_ids ?? []} />
      </div>
    </Card>
  );
}

function ChunkIdList({ title, ids }: { title: string; ids: string[] }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase text-muted-foreground">{title}</div>
      {ids.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">None</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {ids.map((id) => (
            <Badge key={id}>{id}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}
