import benchmarkResults from "@/lib/benchmark-results.json";
import { AppShell } from "@/components/dashboard/app-shell";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/utils";

type BenchmarkRow = {
  strategy: string;
  citation_support: number;
  unsupported_claim_rate: number;
  failure_rate: number;
  retrieval_miss_rate: number;
  average_tokens: number;
  average_latency_ms: number;
  average_cost_usd: number;
};

type QuestionResult = {
  strategy: string;
  question_id: string;
  question: string;
  failure_type: string;
  citation_support: number;
  unsupported_claim_rate: number;
  latency_ms: number;
  cost_usd: number;
};

const data = benchmarkResults as {
  dataset: string;
  generated_at: string;
  ranked_strategies: BenchmarkRow[];
  question_results: QuestionResult[];
  notes: string[];
  website_charts?: Record<string, string>;
};

function formatCost(value: number) {
  return `$${value.toFixed(6)}`;
}

export default function BenchmarksPage() {
  const ranked = data.ranked_strategies;
  const best = ranked[0];
  const cheapest = [...ranked].sort((a, b) => a.average_cost_usd - b.average_cost_usd)[0];
  const fastest = [...ranked].sort((a, b) => a.average_latency_ms - b.average_latency_ms)[0];
  const charts = data.website_charts ?? {};

  return (
    <AppShell>
      <PageHeader
        title="Benchmarks"
        description="Reproducible strategy comparisons for public reports, website tables, and blog charts."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Best Citation Support"
          value={formatPercent(best.citation_support)}
          detail={best.strategy}
        />
        <MetricCard
          label="Lowest Cost"
          value={formatCost(cheapest.average_cost_usd)}
          detail={cheapest.strategy}
        />
        <MetricCard
          label="Lowest Latency"
          value={`${fastest.average_latency_ms.toFixed(0)} ms`}
          detail={fastest.strategy}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Strategy Results</CardTitle>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3">Strategy</th>
                  <th className="py-2 pr-3">Support</th>
                  <th className="py-2 pr-3">Unsupported</th>
                  <th className="py-2 pr-3">Failure</th>
                  <th className="py-2 pr-3">Miss</th>
                  <th className="py-2 pr-3">Tokens</th>
                  <th className="py-2 pr-3">Latency</th>
                  <th className="py-2 pr-3">Cost</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((row) => (
                  <tr key={row.strategy} className="border-b last:border-0">
                    <td className="py-3 pr-3 font-medium">{row.strategy}</td>
                    <td className="py-3 pr-3">{formatPercent(row.citation_support)}</td>
                    <td className="py-3 pr-3">{formatPercent(row.unsupported_claim_rate)}</td>
                    <td className="py-3 pr-3">{formatPercent(row.failure_rate)}</td>
                    <td className="py-3 pr-3">{formatPercent(row.retrieval_miss_rate)}</td>
                    <td className="py-3 pr-3">{row.average_tokens.toFixed(0)}</td>
                    <td className="py-3 pr-3">{row.average_latency_ms.toFixed(0)} ms</td>
                    <td className="py-3 pr-3">{formatCost(row.average_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Report Notes</CardTitle>
          </CardHeader>
          <div className="space-y-3 text-sm text-muted-foreground">
            <div>
              <span className="font-medium text-foreground">Dataset:</span> {data.dataset}
            </div>
            <div>
              <span className="font-medium text-foreground">Run:</span> {data.generated_at}
            </div>
            {data.notes.map((note) => (
              <p key={note}>{note}</p>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {[
          ["Citation Support", charts.citation_support],
          ["Failure Rate", charts.failure_rate],
          ["Average Cost", charts.average_cost_usd]
        ].map(([title, src]) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            {src ? <img src={src} alt={`${title} chart`} className="w-full rounded-md border bg-white" /> : null}
          </Card>
        ))}
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Question-Level Sample</CardTitle>
        </CardHeader>
        <div className="grid gap-3">
          {data.question_results.slice(0, 8).map((row) => (
            <div key={`${row.strategy}-${row.question_id}`} className="rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-medium">{row.question}</div>
                <div className="text-xs text-muted-foreground">{row.strategy}</div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                {row.failure_type} | support {formatPercent(row.citation_support)} | unsupported{" "}
                {formatPercent(row.unsupported_claim_rate)} | {row.latency_ms.toFixed(0)} ms |{" "}
                {formatCost(row.cost_usd)}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}

