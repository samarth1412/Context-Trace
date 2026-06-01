import { UploadForm } from "@/components/playground/upload-form";
import { SiteShell } from "@/components/site/site-shell";
import { ButtonLink } from "@/components/ui/button";

export default function PlaygroundUploadPage() {
  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-6 max-w-3xl">
          <div className="text-sm font-semibold uppercase text-primary">Playground</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">Upload documents.</h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            Index PDF, TXT, and Markdown files for hosted playground retrieval.
          </p>
        </header>
        <div className="mb-4">
          <ButtonLink href="/playground">Back to Playground</ButtonLink>
        </div>
        <UploadForm />
      </main>
    </SiteShell>
  );
}
