from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace


class VerifyReportGenerator:
    def generate(self, result: dict[str, Any], trace: RAGTrace, *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result, trace), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any], trace: RAGTrace) -> str:
        summary = result.get("summary") or {}
        claims = list(result.get("claims") or [])
        abstention = result.get("abstention") or {}
        diagnostics = result.get("diagnostics") or {}
        return HTML_TEMPLATE.format(
            query=escape(_string(result.get("query"))),
            answer=escape(_string(result.get("answer"))),
            summary_cards=_summary_cards(summary),
            failure_type=escape(_string(summary.get("failure_type") or diagnostics.get("failure_type"))),
            suggested_fix=escape(_string(summary.get("suggested_fix") or diagnostics.get("suggested_fix"))),
            claim_rows=_claim_rows(claims),
            evidence_cards=_evidence_cards(claims),
            unsupported_claims=_unsupported_claims(claims),
            citation_mismatches=_citation_mismatches(claims),
            contexts=_contexts(trace),
            why_failed=_why_failed(claims, abstention),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Failure Type", summary.get("failure_type", "unknown")),
        ("Total Claims", summary.get("total_claims", 0)),
        ("Supported", summary.get("supported", 0)),
        ("Partially Supported", summary.get("partially_supported", 0)),
        ("Unsupported", summary.get("unsupported", 0)),
        ("Unverifiable", summary.get("unverifiable", 0)),
        ("Contradicted", summary.get("contradicted", 0)),
        ("Support Rate", summary.get("support_rate", 0)),
        ("Unsupported Claim Rate", summary.get("unsupported_claim_rate", 0)),
        ("Citation Mismatches", summary.get("citation_mismatches", 0)),
        ("Should Abstain", summary.get("should_abstain", False)),
    ]
    return "\n".join(
        """
        <div class="card">
          <div class="label">{label}</div>
          <div class="value">{value}</div>
        </div>
        """.format(label=escape(label), value=escape(_string(value)))
        for label, value in cards
    )


def _claim_rows(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<tr><td colspan=\"6\" class=\"muted\">No factual claims were extracted.</td></tr>"
    rows = []
    for claim in claims:
        rows.append(
            """
            <tr>
              <td>{claim_id}</td>
              <td>{claim}</td>
              <td><span class="badge verdict-{verdict}">{verdict}</span></td>
              <td>{confidence}</td>
              <td>{context_id}</td>
              <td><span class="badge citation-{citation}">{citation}</span></td>
            </tr>
            """.format(
                claim_id=escape(_string(claim.get("claim_id"))),
                claim=escape(_string(claim.get("claim"))),
                verdict=escape(_string(claim.get("verdict"))),
                confidence=escape(_string(claim.get("confidence"))),
                context_id=escape(_string(claim.get("best_context_id"))),
                citation=escape(_string(claim.get("citation_status"))),
            )
        )
    return "\n".join(rows)


def _evidence_cards(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<p class=\"muted\">No evidence cards to show.</p>"
    cards = []
    for claim in claims:
        cards.append(
            """
            <article class="item">
              <div class="item-meta">{claim_id} | {verdict} | score {score}</div>
              <h3>{claim}</h3>
              <p>{evidence}</p>
              <p class="muted">Matched terms: {terms}</p>
              <p>{reason}</p>
            </article>
            """.format(
                claim_id=escape(_string(claim.get("claim_id"))),
                verdict=escape(_string(claim.get("verdict"))),
                score=escape(_string(claim.get("best_score"))),
                claim=escape(_string(claim.get("claim"))),
                evidence=_highlight_terms(
                    _string(claim.get("evidence")) or "No evidence snippet found.",
                    claim.get("matched_terms") or [],
                ),
                terms=escape(", ".join(claim.get("matched_terms") or []) or "none"),
                reason=escape(_string(claim.get("reason"))),
            )
        )
    return "\n".join(cards)


def _unsupported_claims(claims: list[dict[str, Any]]) -> str:
    failures = [
        claim
        for claim in claims
        if claim.get("verdict") in {"unsupported", "contradicted", "unverifiable", "partially_supported"}
    ]
    if not failures:
        return "<p class=\"muted\">No partial, unsupported, contradicted, or unverifiable claims detected.</p>"
    return "\n".join(
        """
        <article class="item">
          <div class="item-meta">{claim_id} | {verdict}</div>
          <p>{claim}</p>
          <p>{reason}</p>
        </article>
        """.format(
            claim_id=escape(_string(claim.get("claim_id"))),
            verdict=escape(_string(claim.get("verdict"))),
            claim=escape(_string(claim.get("claim"))),
            reason=escape(_string(claim.get("reason"))),
        )
        for claim in failures
    )


def _citation_mismatches(claims: list[dict[str, Any]]) -> str:
    mismatches = [claim for claim in claims if claim.get("citation_status") != "citation_ok"]
    if not mismatches:
        return "<p class=\"muted\">All supplied citations support their matched claims.</p>"
    return "\n".join(
        """
        <article class="item">
          <div class="item-meta">{claim_id} | cited {source}</div>
          <p>{claim}</p>
          <p><strong>{status}</strong></p>
          <p class="muted">Best supporting context: {best_context}</p>
        </article>
        """.format(
            claim_id=escape(_string(claim.get("claim_id"))),
            source=escape(_string(claim.get("citation_source_id") or "none")),
            claim=escape(_string(claim.get("claim"))),
            status=escape(_string(claim.get("citation_status"))),
            best_context=escape(_string(claim.get("best_context_id") or "none found")),
        )
        for claim in mismatches
    )


def _contexts(trace: RAGTrace) -> str:
    if not trace.contexts:
        return "<p class=\"muted\">No retrieved contexts were supplied.</p>"
    return "\n".join(
        """
        <article class="item">
          <div class="item-meta">{context_id} | {metadata}</div>
          <p>{text}</p>
        </article>
        """.format(
            context_id=escape(context.id),
            metadata=escape(json.dumps(context.metadata, sort_keys=True) if context.metadata else "no metadata"),
            text=escape(context.text),
        )
        for context in trace.contexts
    )


def _why_failed(claims: list[dict[str, Any]], abstention: dict[str, Any]) -> str:
    explanations = []
    for claim in claims:
        verdict = claim.get("verdict")
        if verdict == "unsupported":
            explanations.append(
                "The answer claimed %s, but none of the retrieved contexts provide enough support. This is likely an unsupported synthesis failure."
                % _quote(claim.get("claim"))
            )
        elif verdict == "contradicted":
            explanations.append(
                "The answer claimed %s, but the strongest retrieved evidence appears to conflict with it."
                % _quote(claim.get("claim"))
            )
        elif verdict == "unverifiable":
            explanations.append(
                "The answer claimed %s, but the retrieved evidence is too weak or ambiguous to verify it."
                % _quote(claim.get("claim"))
            )
        elif verdict == "partially_supported":
            explanations.append(
                "The answer claimed %s, but the retrieved evidence only supports part of that claim."
                % _quote(claim.get("claim"))
            )

    for claim in claims:
        if claim.get("citation_status") == "claim_supported_by_different_source":
            explanations.append(
                "A claim was supported by %s, but the supplied citation pointed to %s."
                % (
                    _string(claim.get("best_context_id")),
                    _string(claim.get("citation_source_id")),
                )
            )
        elif claim.get("citation_status") == "cited_source_does_not_support_claim":
            explanations.append(
                "A supplied citation pointed to %s, but that source did not support the cited claim."
                % _string(claim.get("citation_source_id"))
            )

    if abstention.get("should_abstain"):
        explanations.append(_string(abstention.get("reason")))

    if not explanations:
        explanations.append("No claim-level evidence failure was detected by the local verifier.")

    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(item) for item in explanations)


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": result.get("summary"),
        "abstention": result.get("abstention"),
        "diagnostics": result.get("diagnostics"),
        "claims": result.get("claims"),
    }


def _highlight_terms(text: str, terms: list[str]) -> str:
    escaped = escape(text)
    normalized_terms = [
        re.escape(escape(str(term)))
        for term in terms
        if str(term).strip()
    ]
    if not normalized_terms:
        return escaped
    pattern = re.compile(r"\b(%s)\b" % "|".join(sorted(set(normalized_terms), key=len, reverse=True)), re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", escaped)


def _quote(value: Any) -> str:
    return '"%s"' % _string(value)


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Verification Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --subtle: #fbfcfe;
      --text: #202832;
      --muted: #657286;
      --line: #d9e0ea;
      --ok: #176f44;
      --warn: #946200;
      --bad: #b42318;
      --accent: #2458d3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1160px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 1px solid var(--line); margin-bottom: 22px; padding-bottom: 18px; }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    h3 {{ font-size: 15px; margin-bottom: 8px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }}
    .card, .item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--subtle);
      padding: 12px;
    }}
    .item + .item {{ margin-top: 10px; }}
    .label, .item-meta {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .value {{ margin-top: 4px; font-size: 18px; overflow-wrap: anywhere; }}
    .muted {{ color: var(--muted); }}
    .answer, .item p {{ white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #eef2f7;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .verdict-supported, .citation-citation_ok {{ color: var(--ok); background: #e9f7ef; }}
    .verdict-unverifiable, .verdict-partially_supported, .citation-claim_has_no_citation {{ color: var(--warn); background: #fff7df; }}
    .verdict-unsupported, .verdict-contradicted,
    .citation-cited_source_missing,
    .citation-cited_source_does_not_support_claim {{ color: var(--bad); background: #fdeceb; }}
    pre {{
      margin: 0;
      overflow: auto;
      background: #101828;
      color: #f8fafc;
      border-radius: 8px;
      padding: 14px;
      font-size: 13px;
    }}
    mark {{
      background: #fff0a6;
      color: inherit;
      border-radius: 3px;
      padding: 0 2px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ContextTrace Verification Report</h1>
      <p class="muted">Local claim-level evidence verification for a portable RAG trace.</p>
    </header>

    <section>
      <h2>Reliability Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Suggested Fix</h2>
      <p><strong>{failure_type}</strong></p>
      <p>{suggested_fix}</p>
    </section>

    <section>
      <h2>Query</h2>
      <p>{query}</p>
      <h2>Answer</h2>
      <p class="answer">{answer}</p>
    </section>

    <section>
      <h2>Claim Support Overview</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Claim</th>
            <th>Verdict</th>
            <th>Confidence</th>
            <th>Best Context</th>
            <th>Citation</th>
          </tr>
        </thead>
        <tbody>{claim_rows}</tbody>
      </table>
      <div>{evidence_cards}</div>
    </section>

    <section>
      <h2>Unsupported Claims</h2>
      {unsupported_claims}
    </section>

    <section>
      <h2>Citation Mismatches</h2>
      {citation_mismatches}
    </section>

    <section>
      <h2>Retrieved Contexts</h2>
      {contexts}
    </section>

    <section>
      <h2>Why This Failed</h2>
      {why_failed}
    </section>

    <section>
      <h2>Raw JSON Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
