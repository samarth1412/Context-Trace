import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { TraceChunk } from "@/lib/types";

export function ChunkList({
  title,
  chunks
}: {
  title: string;
  chunks: TraceChunk[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="grid gap-3">
        {chunks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No chunks logged.</p>
        ) : (
          chunks.map((chunk) => (
            <article key={chunk.id} className="rounded-md border p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>{chunk.chunk_id}</span>
                {chunk.source ? <span>{chunk.source}</span> : null}
                {typeof chunk.relevance_score === "number" ? <span>score {chunk.relevance_score}</span> : null}
                {chunk.selected ? <span>selected</span> : null}
              </div>
              <p className="whitespace-pre-wrap text-sm">{chunk.content}</p>
            </article>
          ))
        )}
      </div>
    </Card>
  );
}
