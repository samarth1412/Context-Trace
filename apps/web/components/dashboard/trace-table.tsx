import Link from "next/link";
import { SeverityBadge } from "@/components/dashboard/status-badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import type { TraceSummary } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

export function TraceTable({ traces }: { traces: TraceSummary[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trace List</CardTitle>
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase text-muted-foreground">
              <th className="py-2 pr-4 font-medium">Trace</th>
              <th className="py-2 pr-4 font-medium">Failure</th>
              <th className="py-2 pr-4 font-medium">Score</th>
              <th className="py-2 pr-4 font-medium">Severity</th>
              <th className="py-2 pr-4 font-medium">Citation Support</th>
              <th className="py-2 pr-4 font-medium">Unsupported Claims</th>
              <th className="py-2 pr-4 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((trace) => (
              <tr key={trace.id} className="border-b last:border-0">
                <td className="max-w-md py-3 pr-4">
                  <Link href={`/traces/${trace.id}`} className="font-medium hover:underline">
                    {trace.query}
                  </Link>
                  <div className="mt-1 text-xs text-muted-foreground">{trace.id}</div>
                </td>
                <td className="py-3 pr-4">{trace.failure_type}</td>
                <td className="py-3 pr-4">
                  {trace.reliability.score} ({trace.reliability.grade})
                </td>
                <td className="py-3 pr-4">
                  <SeverityBadge severity={trace.severity} />
                </td>
                <td className="py-3 pr-4">{formatPercent(trace.citation_support)}</td>
                <td className="py-3 pr-4">{formatPercent(trace.unsupported_claim_rate)}</td>
                <td className="whitespace-nowrap py-3 pr-4 text-muted-foreground">
                  {new Date(trace.updated_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
