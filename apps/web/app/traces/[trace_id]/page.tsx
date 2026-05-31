import { AppShell } from "@/components/dashboard/app-shell";
import { ChunkList } from "@/components/dashboard/chunk-list";
import { CitationCards } from "@/components/dashboard/citation-cards";
import { FailureCard } from "@/components/dashboard/failure-card";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { PolicyCard } from "@/components/dashboard/policy-card";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { getTraceDetail } from "@/lib/api";
import type { ContextPolicyMetadata } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

export default async function TraceDetailPage({
  params
}: {
  params: Promise<{ trace_id: string }>;
}) {
  const { trace_id } = await params;
  const trace = await getTraceDetail(trace_id);
  const checks = trace.data.evaluation?.citation_checks ?? trace.data.citation_checks;
  const avgSupport =
    checks.reduce((sum, check) => sum + (check.support_score ?? 0), 0) / Math.max(checks.length, 1);
  const selected = trace.data.chunks.filter((chunk) => chunk.selected);
  const policy = readContextPolicy(trace.data.metadata);
  const droppedChunkIds = new Set(policy?.dropped_chunk_ids ?? []);
  const dropped = trace.data.chunks.filter(
    (chunk) => !chunk.selected || droppedChunkIds.has(chunk.chunk_id)
  );
  const usage = trace.data.answer?.usage ?? {};

  return (
    <AppShell>
      <PageHeader
        title="Trace Detail"
        description={trace.data.query}
        source={trace.source}
        error={trace.error}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Citation Support" value={formatPercent(avgSupport)} detail={`${checks.length} checks`} />
        <MetricCard label="Selected Context" value={String(selected.length)} detail={`${trace.data.chunks.length} retrieved chunks`} />
        <MetricCard
          label="Token Usage"
          value={String(usage.total_tokens ?? 0)}
          detail={`${usage.prompt_tokens ?? 0} prompt, ${usage.completion_tokens ?? 0} completion`}
        />
      </div>

      <div className="mt-4 grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <p className="whitespace-pre-wrap text-sm">{trace.data.answer?.answer ?? "No answer logged."}</p>
        </Card>
        <PolicyCard policy={policy} />
        <FailureCard failure={trace.data.evaluation?.failure} />
        <CitationCards checks={checks} />
        <ChunkList title="Selected Context" chunks={selected} />
        <ChunkList title="Dropped Chunks" chunks={dropped} />
        <ChunkList title="Retrieved Chunks" chunks={trace.data.chunks} />
      </div>
    </AppShell>
  );
}

function readContextPolicy(metadata?: Record<string, unknown>): ContextPolicyMetadata | null {
  const value = metadata?.context_policy;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as ContextPolicyMetadata;
}
