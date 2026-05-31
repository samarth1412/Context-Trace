"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AlertCircle, BarChart3, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { PlaygroundCompareResponse, RetrievalStrategyName } from "@/lib/types";
import { formatDecimal, formatPercent } from "@/lib/utils";

const API_URL = (process.env.NEXT_PUBLIC_CONTEXTTRACE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

const STRATEGIES: Array<{ value: RetrievalStrategyName; label: string }> = [
  { value: "dense_top_k", label: "Dense" },
  { value: "bm25_top_k", label: "BM25" },
  { value: "hybrid", label: "Hybrid" },
  { value: "hybrid_rerank", label: "Hybrid Rerank" }
];

export function StrategyComparison() {
  const [apiKey, setApiKey] = useState("ctx_test");
  const [query, setQuery] = useState("What is the refund policy?");
  const [topK, setTopK] = useState(5);
  const [strategies, setStrategies] = useState<RetrievalStrategyName[]>(
    STRATEGIES.map((strategy) => strategy.value)
  );
  const [result, setResult] = useState<PlaygroundCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function toggleStrategy(strategy: RetrievalStrategyName) {
    setStrategies((current) =>
      current.includes(strategy)
        ? current.filter((value) => value !== strategy)
        : [...current, strategy]
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (strategies.length === 0) {
      setError("Select at least one strategy.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/v1/playground/compare`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query, top_k: topK, strategies })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Comparison failed with ${response.status}`);
      }
      setResult((await response.json()) as PlaygroundCompareResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Strategy Comparison</CardTitle>
      </CardHeader>
      <form className="grid gap-4" onSubmit={onSubmit}>
        <div className="grid gap-3 md:grid-cols-[1fr_120px]">
          <label className="grid gap-2 text-sm">
            <span className="font-medium">API Key</span>
            <input
              className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm">
            <span className="font-medium">Top K</span>
            <input
              className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              min={1}
              max={20}
              type="number"
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
          </label>
        </div>

        <label className="grid gap-2 text-sm">
          <span className="font-medium">Query</span>
          <textarea
            className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <div className="flex flex-wrap gap-3">
          {STRATEGIES.map((strategy) => (
            <label
              key={strategy.value}
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
            >
              <input
                checked={strategies.includes(strategy.value)}
                onChange={() => toggleStrategy(strategy.value)}
                type="checkbox"
              />
              <span>{strategy.label}</span>
            </label>
          ))}
        </div>

        <button
          className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={loading}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
          Compare
        </button>
      </form>

      {error ? (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {result ? <ComparisonTable result={result} /> : null}
    </Card>
  );
}

function ComparisonTable({ result }: { result: PlaygroundCompareResponse }) {
  return (
    <div className="mt-5 overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b text-xs uppercase text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Strategy</th>
            <th className="py-2 pr-4 font-medium">Citation Support</th>
            <th className="py-2 pr-4 font-medium">Unsupported Claims</th>
            <th className="py-2 pr-4 font-medium">Failure</th>
            <th className="py-2 pr-4 font-medium">Tokens</th>
            <th className="py-2 pr-4 font-medium">Latency</th>
            <th className="py-2 pr-4 font-medium">Trace</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <tr key={row.trace_id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 font-medium">{row.strategy}</td>
              <td className="py-3 pr-4">{formatPercent(row.metrics.citation_support)}</td>
              <td className="py-3 pr-4">{formatPercent(row.metrics.unsupported_claim_rate)}</td>
              <td className="py-3 pr-4">
                <Badge tone={row.metrics.failure_type === "no_failure_detected" ? "green" : "amber"}>
                  {row.metrics.failure_type}
                </Badge>
              </td>
              <td className="py-3 pr-4">{tokenCount(row.metrics.token_usage)}</td>
              <td className="py-3 pr-4">{formatDecimal(row.metrics.latency_ms)} ms</td>
              <td className="py-3 pr-4">
                <Link className="font-medium text-primary" href={`/traces/${row.trace_id}`}>
                  Open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function tokenCount(usage: Record<string, unknown>) {
  const total = usage.total_tokens;
  return typeof total === "number" ? total.toLocaleString() : "n/a";
}
