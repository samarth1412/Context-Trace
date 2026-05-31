import { SeverityBadge } from "@/components/dashboard/status-badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { FailurePayload } from "@/lib/types";

export function FailureCard({ failure }: { failure?: FailurePayload | null }) {
  if (!failure) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Failure Diagnosis</CardTitle>
        </CardHeader>
        <p className="text-sm text-muted-foreground">No failure report available.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Failure Diagnosis</CardTitle>
        <SeverityBadge severity={failure.severity} />
      </CardHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Failure Type</div>
          <div className="mt-1 text-sm font-medium">{failure.failure_type}</div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Root Cause</div>
          <p className="mt-1 text-sm">{failure.root_cause}</p>
        </div>
        <div className="md:col-span-2">
          <div className="text-xs font-medium uppercase text-muted-foreground">Suggested Fix</div>
          <p className="mt-1 text-sm">{failure.suggested_fix}</p>
        </div>
      </div>
    </Card>
  );
}
