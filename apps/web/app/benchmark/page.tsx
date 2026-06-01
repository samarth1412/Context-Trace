import benchmarkResults from "@/lib/benchmark-results.json";
import { BarChart3, Clock3, DollarSign, ShieldCheck } from "lucide-react";
import { SiteShell } from "@/components/site/site-shell";
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

const data = benchmarkResults as {
  dataset: string;
  generated_at: string;
  ranked_strategies: BenchmarkRow[];
  notes: string[];
  website_charts?: Record<string, string>;
};

function formatCost(value: number) {
  return `$${value.toFixed(6)}`;
}

export default function BenchmarkPage() {
  const ranked = data.ranked_strategies;
  const best = ranked[0];
  const cheapest = [...ranked].sort((a, b) => a.average_cost_usd - b.average_cost_usd)[0];
  const fastest = [...ranked].sort((a, b) => a.average_latency_ms - b.average_latency_ms)[0];
  const charts = data.website_charts ?? {};

  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-8 max-w-4xl">
          <div className="text-sm font-semibold uppercase text-primary">Benchmark</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">
            Reproducible RAG strategy comparisons.
          </h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            ContextTrace benchmarks compare retrieval strategies on citation support, unsupported
            claim rate, failures, retrieval misses, cost, tokens, and latency. The checked-in public
            report is deterministic, so website and blog charts are stable.
          </p>
        </header>

        <div className="grid gap-4 md:grid-cols-3">
          <Metric icon={ShieldCheck} label="Best citation support" value={formatPercent(best.citation_support)} detail={best.strategy} />
          <Metric icon={DollarSign} label="Lowest cost" value={formatCost(cheapest.average_cost_usd)} detail={cheapest.strategy} />
          <Metric icon={Clock3} label="Lowest latency" value={`${fastest.average_latency_ms.toFixed(0)} ms`} detail={fastest.strategy} />
        </div>

        <section className="mt-8 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <Card>
            <CardHeader>
              <CardTitle>Strategy Results</CardTitle>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-left text-sm">
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
              <CardTitle>Honest Tradeoffs</CardTitle>
            </CardHeader>
            <div className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>
                Dataset: <span className="font-medium text-foreground">{data.dataset}</span>
              </p>
              {data.notes.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          </Card>
        </section>

        <section className="mt-8 grid gap-4 lg:grid-cols-3">
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
        </section>
      </main>
    </SiteShell>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: typeof BarChart3;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card>
      <Icon className="mb-3 h-5 w-5 text-primary" aria-hidden="true" />
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{detail}</div>
    </Card>
  );
}

