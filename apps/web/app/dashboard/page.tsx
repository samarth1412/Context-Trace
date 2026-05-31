import Link from "next/link";
import { AppShell } from "@/components/dashboard/app-shell";
import { FailureDistributionChart } from "@/components/dashboard/failure-distribution-chart";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { TraceTable } from "@/components/dashboard/trace-table";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { getDashboardData } from "@/lib/api";
import { formatPercent } from "@/lib/utils";

export default async function DashboardPage() {
  const { traces, evalSummary } = await getDashboardData();
  const evaluated = evalSummary.data.evaluated_trace_count;
  const worstTrace = evalSummary.data.worst_traces[0];

  return (
    <AppShell>
      <PageHeader
        title="Dashboard"
        description="Reliability overview across traced RAG runs and eval-set summaries."
        source={traces.source === "backend" && evalSummary.source === "backend" ? "backend" : "mock"}
        error={traces.error ?? evalSummary.error}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Average Citation Support"
          value={formatPercent(evalSummary.data.avg_citation_support)}
          detail={`${evaluated} evaluated traces`}
        />
        <MetricCard
          label="Unsupported Claim Rate"
          value={formatPercent(evalSummary.data.unsupported_claim_rate)}
          detail={`${evalSummary.data.unevaluated_trace_count} unevaluated linked traces`}
        />
        <MetricCard
          label="Worst Severity"
          value={worstTrace?.severity ?? "none"}
          detail={worstTrace?.failure_type ?? "no failures detected"}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_360px]">
        <TraceTable traces={traces.data} />
        <div className="grid gap-4">
          <FailureDistributionChart distribution={evalSummary.data.failure_type_distribution} />
          <Card>
            <CardHeader>
              <CardTitle>Worst Traces</CardTitle>
            </CardHeader>
            <div className="space-y-3">
              {evalSummary.data.worst_traces.map((trace) => (
                <Link
                  key={trace.trace_id}
                  href={`/traces/${trace.trace_id}`}
                  className="block rounded-md border p-3 text-sm hover:bg-muted"
                >
                  <div className="font-medium">{trace.question}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {trace.failure_type} | {trace.severity} | support {formatPercent(trace.citation_support)}
                  </div>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
