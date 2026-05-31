import { AppShell } from "@/components/dashboard/app-shell";
import { PageHeader } from "@/components/dashboard/page-header";
import { QueryConsole } from "@/components/playground/query-console";
import { ButtonLink } from "@/components/ui/button";

export default function PlaygroundPage() {
  return (
    <AppShell>
      <PageHeader
        title="Playground"
        description="Run hosted RAG queries against uploaded documents and inspect the generated trace."
      />
      <div className="mb-4">
        <ButtonLink href="/playground/upload">Upload Documents</ButtonLink>
      </div>
      <QueryConsole />
    </AppShell>
  );
}
