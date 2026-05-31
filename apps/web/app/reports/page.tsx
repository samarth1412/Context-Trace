import Link from "next/link";
import { AppShell } from "@/components/dashboard/app-shell";
import { FailureDistributionChart } from "@/components/dashboard/failure-distribution-chart";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { getEvalSummary } from "@/lib/api";
import { formatPercent } from "@/lib/utils";

export default async function ReportsPage() {
  const summary = await getEvalSummary();

  return (
    <AppShell>
      <PageHeader
        title="Reports"
        description="Eval-set reliability summary and traces that need follow-up."
        source={summary.source}
        error={summary.error}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Average Citation Support"
          value={formatPercent(summary.data.avg_citation_support)}
          detail={summary.data.name}
        />
        <MetricCard
          label="Unsupported Claim Rate"
          value={formatPercent(summary.data.unsupported_claim_rate)}
          detail={`${summary.data.total_questions} eval questions`}
        />
        <MetricCard
          label="Evaluated Traces"
          value={String(summary.data.evaluated_trace_count)}
          detail={`${summary.data.unevaluated_trace_count} unevaluated`}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[360px_1fr]">
        <FailureDistributionChart distribution={summary.data.failure_type_distribution} />
        <Card>
          <CardHeader>
            <CardTitle>Worst Traces</CardTitle>
          </CardHeader>
          <div className="grid gap-3">
            {summary.data.worst_traces.map((trace) => (
              <Link
                key={trace.trace_id}
                href={`/traces/${trace.trace_id}`}
                className="rounded-md border p-3 text-sm hover:bg-muted"
              >
                <div className="font-medium">{trace.question}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {trace.failure_type} | {trace.severity} | unsupported {formatPercent(trace.unsupported_claim_rate)}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{trace.root_cause}</p>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
