import { Badge } from "@/components/ui/badge";
import type { CitationVerdict, Severity } from "@/lib/types";

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const tone = severity === "high" ? "red" : severity === "medium" ? "amber" : severity === "low" ? "blue" : "green";
  return <Badge tone={tone}>{severity}</Badge>;
}

export function VerdictBadge({ verdict }: { verdict: CitationVerdict | string }) {
  const tone =
    verdict === "directly_supported"
      ? "green"
      : verdict === "partially_supported" || verdict === "not_enough_info"
        ? "amber"
        : verdict === "unsupported" || verdict === "contradicted"
          ? "red"
          : "neutral";
  return <Badge tone={tone}>{verdict}</Badge>;
}
