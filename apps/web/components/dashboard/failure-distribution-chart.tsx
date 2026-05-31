import { Card, CardHeader, CardTitle } from "@/components/ui/card";

export function FailureDistributionChart({
  distribution
}: {
  distribution: Record<string, number>;
}) {
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Failure Distribution</CardTitle>
      </CardHeader>
      <div className="space-y-3">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No evaluated traces yet.</p>
        ) : (
          entries.map(([failureType, count]) => {
            const percent = total ? (count / total) * 100 : 0;
            return (
              <div key={failureType}>
                <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                  <span className="truncate">{failureType}</span>
                  <span className="text-muted-foreground">{count}</span>
                </div>
                <div className="h-2 rounded-sm bg-muted">
                  <div className="h-2 rounded-sm bg-primary" style={{ width: `${percent}%` }} />
                </div>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
