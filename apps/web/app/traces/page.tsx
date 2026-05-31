import { AppShell } from "@/components/dashboard/app-shell";
import { PageHeader } from "@/components/dashboard/page-header";
import { TraceTable } from "@/components/dashboard/trace-table";
import { getTraceSummaries } from "@/lib/api";

export default async function TracesPage() {
  const traces = await getTraceSummaries();

  return (
    <AppShell>
      <PageHeader
        title="Traces"
        description="Recent RAG traces with citation support, unsupported claim rate, and failure labels."
        source={traces.source}
        error={traces.error}
      />
      <TraceTable traces={traces.data} />
    </AppShell>
  );
}
