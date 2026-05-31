import { VerdictBadge } from "@/components/dashboard/status-badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { CitationCheck } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

export function CitationCards({ checks }: { checks: CitationCheck[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Citation Verification</CardTitle>
      </CardHeader>
      <div className="grid gap-3">
        {checks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No citation checks logged.</p>
        ) : (
          checks.map((check, index) => {
            const verdict = check.verdict ?? check.support_status ?? "pending";
            const reason = check.reason ?? check.rationale ?? "";
            return (
              <article key={`${check.source_chunk_id}-${index}`} className="rounded-md border p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <VerdictBadge verdict={verdict} />
                  <span className="text-xs text-muted-foreground">source {check.source_chunk_id}</span>
                  {typeof check.support_score === "number" ? (
                    <span className="text-xs text-muted-foreground">
                      support {formatPercent(check.support_score)}
                    </span>
                  ) : null}
                </div>
                <p className="text-sm font-medium">{check.claim}</p>
                {reason ? <p className="mt-2 text-sm text-muted-foreground">{reason}</p> : null}
              </article>
            );
          })
        )}
      </div>
    </Card>
  );
}
