import { AppShell } from "@/components/dashboard/app-shell";
import { PageHeader } from "@/components/dashboard/page-header";
import { UploadForm } from "@/components/playground/upload-form";
import { ButtonLink } from "@/components/ui/button";

export default function PlaygroundUploadPage() {
  return (
    <AppShell>
      <PageHeader
        title="Upload Documents"
        description="Index PDF, TXT, and Markdown files for playground retrieval."
      />
      <div className="mb-4">
        <ButtonLink href="/playground">Back to Playground</ButtonLink>
      </div>
      <UploadForm />
    </AppShell>
  );
}
