"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AlertCircle, Loader2, Search } from "lucide-react";
import { CitationCards } from "@/components/dashboard/citation-cards";
import { FailureCard } from "@/components/dashboard/failure-card";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { PlaygroundQueryResponse } from "@/lib/types";
import { formatDecimal } from "@/lib/utils";

const API_URL = (process.env.NEXT_PUBLIC_CONTEXTTRACE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

export function QueryConsole() {
  const [apiKey, setApiKey] = useState("ctx_test");
  const [query, setQuery] = useState("What is the refund policy?");
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<PlaygroundQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
        body: JSON.stringify({ query, top_k: topK })
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

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Playground Query</CardTitle>
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
          <Card>
            <CardHeader>
              <CardTitle>Answer</CardTitle>
              <Link className="text-sm font-medium text-primary" href={`/traces/${result.trace_id}`}>
                Trace
              </Link>
            </CardHeader>
            <p className="whitespace-pre-wrap text-sm leading-6">{result.answer}</p>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <CitationCards checks={result.evaluation.citation_checks} />
            <FailureCard failure={result.evaluation.failure} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Retrieved Chunks</CardTitle>
            </CardHeader>
            <div className="grid gap-3">
              {result.retrieved_chunks.map((chunk) => (
                <article key={chunk.chunk_id} className="rounded-md border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{chunk.source ?? "unknown source"}</span>
                    <span>{formatDecimal(chunk.score)}</span>
                    <span>{chunk.chunk_id}</span>
                  </div>
                  <p className="text-sm leading-6">{chunk.content}</p>
                </article>
              ))}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
