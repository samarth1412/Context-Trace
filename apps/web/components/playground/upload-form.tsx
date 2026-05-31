"use client";

import { ChangeEvent, FormEvent, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Upload } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { PlaygroundDocumentUploadResponse } from "@/lib/types";

const API_URL = (process.env.NEXT_PUBLIC_CONTEXTTRACE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

export function UploadForm() {
  const [apiKey, setApiKey] = useState("ctx_test");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PlaygroundDocumentUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setResult(null);
    setError(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF, TXT, or Markdown file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/v1/playground/documents`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`
        },
        body: formData
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Upload failed with ${response.status}`);
      }
      setResult((await response.json()) as PlaygroundDocumentUploadResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Document Upload</CardTitle>
      </CardHeader>
      <form className="grid gap-4" onSubmit={onSubmit}>
        <label className="grid gap-2 text-sm">
          <span className="font-medium">API Key</span>
          <input
            className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>

        <label className="grid gap-2 text-sm">
          <span className="font-medium">Document</span>
          <input
            className="rounded-md border bg-background px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm"
            type="file"
            accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            onChange={onFileChange}
          />
        </label>

        <button
          className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={loading}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          Upload
        </button>
      </form>

      {error ? (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {result ? (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">{result.filename}</div>
            <div className="text-emerald-800">
              {result.chunk_count} chunks indexed | {result.document_id}
            </div>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
