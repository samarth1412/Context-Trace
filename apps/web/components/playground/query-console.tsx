"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Download, Loader2, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  PlaygroundChunk,
  PlaygroundQueryResponse,
  PlaygroundSampleDataset,
  PlaygroundSampleLoadResponse,
  PlaygroundSamplesResponse,
  RetrievalStrategyName
} from "@/lib/types";
import { formatDecimal, formatPercent } from "@/lib/utils";

const API_URL = (process.env.NEXT_PUBLIC_CONTEXTTRACE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

const STRATEGIES: Array<{ value: RetrievalStrategyName; label: string; detail: string }> = [
  { value: "dense_top_k", label: "Dense", detail: "Fast semantic retrieval" },
  { value: "bm25_top_k", label: "BM25", detail: "Lexical keyword baseline" },
  { value: "hybrid", label: "Hybrid", detail: "Dense + lexical merge" },
  { value: "hybrid_rerank", label: "Hybrid rerank", detail: "Higher precision, more latency" },
  { value: "corrective_rag", label: "Corrective RAG", detail: "Fallback when confidence is weak" },
  { value: "contexttrace_adaptive", label: "Adaptive", detail: "Policy runtime chooses strategy" }
];

export function QueryConsole() {
  const [apiKey, setApiKey] = useState("ctx_test");
  const [query, setQuery] = useState("What is the refund policy?");
  const [topK, setTopK] = useState(5);
  const [strategy, setStrategy] = useState<RetrievalStrategyName>("contexttrace_adaptive");
  const [samples, setSamples] = useState<PlaygroundSampleDataset[]>([]);
  const [sampleStatus, setSampleStatus] = useState<string | null>(null);
  const [result, setResult] = useState<PlaygroundQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sampleLoading, setSampleLoading] = useState<string | null>(null);

  useEffect(() => {
    void loadSamples();
  }, []);

  async function loadSamples() {
    try {
      const response = await fetch(`${API_URL}/v1/playground/samples`, {
        headers: { Authorization: `Bearer ${apiKey}` }
      });
      if (response.ok) {
        const body = (await response.json()) as PlaygroundSamplesResponse;
        setSamples(body.samples);
      }
    } catch {
      setSamples([]);
    }
  }

  async function loadSample(sample: PlaygroundSampleDataset) {
    setSampleLoading(sample.sample_id);
    setError(null);
    setSampleStatus(null);
    try {
      const response = await fetch(`${API_URL}/v1/playground/samples/${sample.sample_id}/load`, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}` }
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Sample load failed with ${response.status}`);
      }
      const body = (await response.json()) as PlaygroundSampleLoadResponse;
      setQuery(body.suggested_queries[0] ?? query);
      setSampleStatus(`${body.name} loaded with ${body.chunk_count} chunks.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sample load failed");
    } finally {
      setSampleLoading(null);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/v1/playground/query`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query, top_k: topK, strategy })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Query failed with ${response.status}`);
      }
      setResult((await response.json()) as PlaygroundQueryResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  function exportReport() {
    if (!result) return;
    const html = renderReportHtml(result, query);
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `contexttrace-playground-${result.trace_id}.html`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Hosted Playground</CardTitle>
        </CardHeader>

        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Playground is for demos. Use the SDK or integrations for production tracing.
        </div>

        {samples.length ? (
          <div className="mb-4 grid gap-3 md:grid-cols-3">
            {samples.map((sample) => (
              <button
                key={sample.sample_id}
                type="button"
                className="rounded-md border bg-background p-3 text-left hover:bg-muted disabled:opacity-60"
                onClick={() => loadSample(sample)}
                disabled={sampleLoading !== null}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">Try {sample.name}</span>
                  {sampleLoading === sample.sample_id ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{sample.description}</p>
              </button>
            ))}
          </div>
        ) : null}

        {sampleStatus ? (
          <div className="mb-4 flex items-start gap-2 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{sampleStatus}</span>
          </div>
        ) : null}

        <form className="grid gap-4" onSubmit={onSubmit}>
          <div className="grid gap-3 md:grid-cols-[1fr_120px]">
            <label className="grid gap-2 text-sm">
              <span className="font-medium">API Key</span>
              <input
                className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                onBlur={() => void loadSamples()}
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
            <span className="font-medium">Strategy</span>
            <select
              className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              value={strategy}
              onChange={(event) => setStrategy(event.target.value as RetrievalStrategyName)}
            >
              {STRATEGIES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label} - {item.detail}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-2 text-sm">
            <span className="font-medium">Query</span>
            <textarea
              className="min-h-28 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <button
            className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={loading}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Run Query
          </button>
        </form>

        {error ? (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}
      </Card>

      {result ? (
        <div className="grid gap-4">
          <div className="grid gap-4 md:grid-cols-4">
            <Metric label="Citation support" value={formatPercent(result.metrics.citation_support)} />
            <Metric label="Unsupported claims" value={formatPercent(result.metrics.unsupported_claim_rate)} />
            <Metric label="Latency" value={`${formatDecimal(result.metrics.latency_ms)} ms`} />
            <Metric label="Est. cost" value={`$${result.metrics.estimated_cost_usd.toFixed(6)}`} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Answer</CardTitle>
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={result.evaluation.failure.failure_type === "no_failure_detected" ? "green" : "amber"}>
                  {result.evaluation.failure.failure_type}
                </Badge>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary"
                  onClick={exportReport}
                >
                  <Download className="h-4 w-4" />
                  Export report
                </button>
                <Link className="text-sm font-medium text-primary" href={`/traces/${result.trace_id}`}>
                  Trace
                </Link>
              </div>
            </CardHeader>
            <p className="whitespace-pre-wrap text-sm leading-6">{result.answer}</p>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Citations">
              {result.evaluation.citation_checks.map((check) => (
                <article key={`${check.claim}-${check.source_chunk_id}`} className="rounded-md border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone={check.support_status === "directly_supported" ? "green" : "amber"}>
                      {check.support_status ?? check.verdict ?? "pending"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{check.source_chunk_id}</span>
                  </div>
                  <p className="text-sm font-medium">{check.claim}</p>
                  <p className="mt-2 text-sm text-muted-foreground">{check.rationale ?? check.reason}</p>
                </article>
              ))}
            </Panel>
            <Panel title="Failure Diagnosis">
              <div className="rounded-md border p-3">
                <div className="mb-2 flex items-center gap-2">
                  <Badge tone={result.evaluation.failure.severity === "none" ? "green" : "amber"}>
                    {result.evaluation.failure.severity}
                  </Badge>
                  <span className="text-sm font-medium">{result.evaluation.failure.failure_type}</span>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">{result.evaluation.failure.root_cause}</p>
                <p className="mt-3 text-sm leading-6">{result.evaluation.failure.suggested_fix}</p>
              </div>
            </Panel>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <ChunkPanel title="Retrieved Chunks" chunks={result.retrieved_chunks} />
            <ChunkPanel title="Selected Context" chunks={result.selected_context} />
            <ChunkPanel title="Dropped Context" chunks={result.dropped_context} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </Card>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="grid gap-3">{children}</div>
    </Card>
  );
}

function ChunkPanel({ title, chunks }: { title: string; chunks: PlaygroundChunk[] }) {
  return (
    <Panel title={`${title} (${chunks.length})`}>
      {chunks.length ? (
        chunks.map((chunk) => (
          <article key={chunk.chunk_id} className="rounded-md border p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{chunk.source ?? "unknown source"}</span>
              <span>{formatDecimal(chunk.score)}</span>
              <span>{chunk.chunk_id}</span>
            </div>
            <p className="text-sm leading-6">{chunk.content}</p>
          </article>
        ))
      ) : (
        <p className="text-sm text-muted-foreground">No chunks in this panel.</p>
      )}
    </Panel>
  );
}

function renderReportHtml(result: PlaygroundQueryResponse, query: string) {
  const escaped = (value: unknown) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  const chunkList = (title: string, chunks: PlaygroundChunk[]) => `
    <h2>${escaped(title)}</h2>
    ${chunks
      .map(
        (chunk) => `
      <article>
        <div><strong>${escaped(chunk.source)}</strong> ${escaped(chunk.chunk_id)} score ${escaped(chunk.score)}</div>
        <p>${escaped(chunk.content)}</p>
      </article>`
      )
      .join("")}
  `;

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ContextTrace Playground Report</title>
  <style>
    body { font-family: Inter, Arial, sans-serif; margin: 40px; color: #172033; line-height: 1.55; }
    h1, h2 { color: #101827; }
    article { border: 1px solid #d7dde8; border-radius: 8px; padding: 12px; margin: 10px 0; }
    .metric { display: inline-block; border: 1px solid #d7dde8; border-radius: 8px; padding: 10px 12px; margin: 4px; }
  </style>
</head>
<body>
  <h1>ContextTrace Playground Report</h1>
  <p><strong>Query:</strong> ${escaped(query)}</p>
  <p><strong>Trace:</strong> ${escaped(result.trace_id)}</p>
  <div class="metric">Citation support: ${formatPercent(result.metrics.citation_support)}</div>
  <div class="metric">Unsupported claims: ${formatPercent(result.metrics.unsupported_claim_rate)}</div>
  <div class="metric">Latency: ${formatDecimal(result.metrics.latency_ms)} ms</div>
  <div class="metric">Estimated cost: $${result.metrics.estimated_cost_usd.toFixed(6)}</div>
  <h2>Answer</h2>
  <p>${escaped(result.answer)}</p>
  <h2>Failure Diagnosis</h2>
  <p><strong>${escaped(result.evaluation.failure.failure_type)}</strong> (${escaped(result.evaluation.failure.severity)})</p>
  <p>${escaped(result.evaluation.failure.root_cause)}</p>
  <p>${escaped(result.evaluation.failure.suggested_fix)}</p>
  ${chunkList("Retrieved Chunks", result.retrieved_chunks)}
  ${chunkList("Selected Context", result.selected_context)}
  ${chunkList("Dropped Context", result.dropped_context)}
</body>
</html>`;
}
