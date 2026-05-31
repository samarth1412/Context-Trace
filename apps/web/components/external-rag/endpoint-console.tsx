"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Play, Plug } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExternalEndpointResponse, ExternalEndpointTestResponse } from "@/lib/types";

const API_URL = (process.env.NEXT_PUBLIC_CONTEXTTRACE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

const defaultHeaders = `{
  "Authorization": "Bearer ..."
}`;

const defaultBodyTemplate = `{
  "question": "{{query}}"
}`;

const defaultResponseMapping = `{
  "answer": "$.answer",
  "citations": "$.sources",
  "retrieved_chunks": "$.contexts"
}`;

export function EndpointConsole() {
  const [apiKey, setApiKey] = useState("ctx_test");
  const [projectId, setProjectId] = useState("");
  const [endpointId, setEndpointId] = useState("");
  const [name, setName] = useState("support-api");
  const [url, setUrl] = useState("https://my-rag-app.com/query");
  const [method, setMethod] = useState<"GET" | "POST">("POST");
  const [headersJson, setHeadersJson] = useState(defaultHeaders);
  const [bodyTemplateJson, setBodyTemplateJson] = useState(defaultBodyTemplate);
  const [responseMappingJson, setResponseMappingJson] = useState(defaultResponseMapping);
  const [query, setQuery] = useState("What is the refund policy?");
  const [registered, setRegistered] = useState<ExternalEndpointResponse | null>(null);
  const [testResult, setTestResult] = useState<ExternalEndpointTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  async function registerEndpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setRegistered(null);

    try {
      const response = await fetch(`${API_URL}/v1/projects/${projectId}/external-endpoints`, {
        method: "POST",
        headers: requestHeaders(apiKey),
        body: JSON.stringify({
          name,
          url,
          method,
          headers: parseJsonObject(headersJson, "Headers"),
          body_template: parseJsonObject(bodyTemplateJson, "Body template"),
          response_mapping: parseJsonObject(responseMappingJson, "Response mapping")
        })
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Endpoint registration failed"));
      }
      const payload = (await response.json()) as ExternalEndpointResponse;
      setRegistered(payload);
      setEndpointId(payload.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Endpoint registration failed");
    } finally {
      setSaving(false);
    }
  }

  async function testEndpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTesting(true);
    setError(null);
    setTestResult(null);

    try {
      const response = await fetch(`${API_URL}/v1/external-endpoints/${endpointId}/test`, {
        method: "POST",
        headers: requestHeaders(apiKey),
        body: JSON.stringify({ query })
      });
      if (!response.ok) {
        throw new Error(await responseError(response, "Endpoint test failed"));
      }
      setTestResult((await response.json()) as ExternalEndpointTestResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Endpoint test failed");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Endpoint Configuration</CardTitle>
        </CardHeader>
        <form className="grid gap-4" onSubmit={registerEndpoint}>
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="API Key" value={apiKey} onChange={setApiKey} />
            <TextField label="Project ID" value={projectId} onChange={setProjectId} />
            <TextField label="Name" value={name} onChange={setName} />
            <TextField label="URL" value={url} onChange={setUrl} />
          </div>

          <label className="grid gap-2 text-sm md:w-44">
            <span className="font-medium">Method</span>
            <select
              className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              value={method}
              onChange={(event) => setMethod(event.target.value as "GET" | "POST")}
            >
              <option value="POST">POST</option>
              <option value="GET">GET</option>
            </select>
          </label>

          <div className="grid gap-3 lg:grid-cols-3">
            <JsonField label="Headers" value={headersJson} onChange={setHeadersJson} />
            <JsonField label="Body Template" value={bodyTemplateJson} onChange={setBodyTemplateJson} />
            <JsonField label="Response Mapping" value={responseMappingJson} onChange={setResponseMappingJson} />
          </div>

          <button
            className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={saving || !projectId}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
            Save Endpoint
          </button>
        </form>

        {registered ? (
          <div className="mt-4 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            <span>Saved endpoint {registered.id}</span>
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test Query</CardTitle>
        </CardHeader>
        <form className="grid gap-4" onSubmit={testEndpoint}>
          <TextField label="Endpoint ID" value={endpointId} onChange={setEndpointId} />
          <label className="grid gap-2 text-sm">
            <span className="font-medium">Query</span>
            <textarea
              className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button
            className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={testing || !endpointId}
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Send Test Query
          </button>
        </form>
      </Card>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {testResult ? <MappedResponse result={testResult} /> : null}
    </div>
  );
}

function MappedResponse({ result }: { result: ExternalEndpointTestResponse }) {
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Mapped Answer</CardTitle>
          <Link className="text-sm font-medium text-primary" href={`/traces/${result.trace_id}`}>
            Trace
          </Link>
        </CardHeader>
        <p className="whitespace-pre-wrap text-sm leading-6">{result.mapped.answer}</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Mapped Citations</CardTitle>
          </CardHeader>
          <div className="grid gap-3">
            {result.mapped.citations.map((citation, index) => (
              <article key={`${citation.source_chunk_id}-${index}`} className="rounded-md border p-3 text-sm">
                <div className="mb-1 font-medium">{citation.source_chunk_id}</div>
                <p className="leading-6">{citation.claim}</p>
              </article>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Mapped Chunks</CardTitle>
          </CardHeader>
          <div className="grid gap-3">
            {result.mapped.retrieved_chunks.map((chunk, index) => (
              <article key={chunk.chunk_id ?? index} className="rounded-md border p-3 text-sm">
                <div className="mb-1 text-xs font-medium text-muted-foreground">
                  {chunk.chunk_id ?? `chunk_${index}`} | {chunk.source ?? "unknown source"}
                </div>
                <p className="leading-6">{chunk.content}</p>
              </article>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium">{label}</span>
      <input
        className="h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function JsonField({
  label,
  value,
  onChange
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium">{label}</span>
      <textarea
        className="min-h-40 rounded-md border bg-background px-3 py-2 font-mono text-xs outline-none focus:border-primary"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function requestHeaders(apiKey: string) {
  return {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json"
  };
}

function parseJsonObject(value: string, label: string) {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

async function responseError(response: Response, fallback: string) {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null;
  return body?.detail ?? `${fallback} with ${response.status}`;
}
