"use client";

import { AppShell } from "@/components/dashboard/app-shell";

export default function TracesError({
  error,
  reset
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <AppShell>
      <div className="rounded-lg border bg-card p-6">
        <h1 className="text-lg font-semibold">Traces failed to load</h1>
        <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
        <button className="mt-4 rounded-md border px-3 py-2 text-sm" onClick={reset}>
          Retry
        </button>
      </div>
    </AppShell>
  );
}
