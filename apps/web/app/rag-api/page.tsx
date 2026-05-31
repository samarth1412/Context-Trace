import { AppShell } from "@/components/dashboard/app-shell";
import { PageHeader } from "@/components/dashboard/page-header";
import { EndpointConsole } from "@/components/external-rag/endpoint-console";

export default function RagApiPage() {
  return (
    <AppShell>
      <PageHeader
        title="RAG APIs"
        description="Configure an existing RAG endpoint, send a test query, and inspect the mapped ContextTrace trace."
      />
      <EndpointConsole />
    </AppShell>
  );
}
