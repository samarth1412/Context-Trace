export function LoadingPanel() {
  return (
    <div className="grid gap-4">
      <div className="h-20 animate-pulse rounded-lg border bg-card" />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="h-28 animate-pulse rounded-lg border bg-card" />
        <div className="h-28 animate-pulse rounded-lg border bg-card" />
        <div className="h-28 animate-pulse rounded-lg border bg-card" />
      </div>
      <div className="h-72 animate-pulse rounded-lg border bg-card" />
    </div>
  );
}
