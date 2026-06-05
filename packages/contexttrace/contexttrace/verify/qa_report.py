from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace


class QAReportGenerator:
    def generate(self, result: dict[str, Any], trace: RAGTrace, *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result, trace), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any], trace: RAGTrace) -> str:
        summary = result.get("summary") or {}
        verification = result.get("verification") or {}
        audit = result.get("audit") or {}
        inspection = result.get("inspection") or {}
        return HTML_TEMPLATE.format(
            query=escape(_string(result.get("query"))),
            answer=escape(_string(result.get("answer"))),
            summary_cards=_summary_cards(summary),
            risk_signals=_risk_signals(summary),
            next_actions=_next_actions(result.get("next_actions") or []),
            inspect_warnings=_inspect_warnings(inspection),
            verify_rows=_verify_rows(list(verification.get("claims") or [])),
            audit_rows=_audit_rows(list(audit.get("claims") or [])),
            contexts=_contexts(trace),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Risk Level", summary.get("risk_level")),
        ("Risk Score", summary.get("risk_score")),
        ("Primary Issue", summary.get("primary_issue")),
        ("Corpus Audited", summary.get("corpus_audited")),
        ("Total Claims", summary.get("total_claims")),
        ("Grounding Rate", summary.get("support_rate")),
        ("Truth Status", "not_assessed"),
        ("Source Freshness", "freshness_unknown"),
        ("Unsupported Rate", summary.get("unsupported_claim_rate")),
        ("Citation Mismatches", summary.get("citation_mismatches")),
        ("Should Abstain", summary.get("should_abstain")),
        ("Audit Label", summary.get("audit_primary_label") or "not_run"),
        ("Inspection Warnings", summary.get("inspect_warnings")),
        ("Verification Failure", summary.get("verification_failure_type")),
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


def _risk_signals(summary: dict[str, Any]) -> str:
    signals = list(summary.get("risk_signals") or [])
    if not signals:
        return "<p class=\"muted\">No QA risk signals were detected.</p>"
    return "<ul>%s</ul>" % "\n".join(
        "<li><strong>{band}</strong> | {title}: {points} points</li>".format(
            band=escape(_string(signal.get("risk_band"))),
            title=escape(_string(signal.get("title"))),
            points=escape(_string(signal.get("points"))),
        )
        for signal in signals
    )


def _next_actions(actions: list[str]) -> str:
    if not actions:
        return "<p class=\"muted\">No action is needed based on this QA run.</p>"
    return "<ol>%s</ol>" % "\n".join("<li>%s</li>" % escape(_string(action)) for action in actions)


def _inspect_warnings(inspection: dict[str, Any]) -> str:
    warnings = list(inspection.get("warnings") or [])
    if not warnings:
        return "<p class=\"muted\">No trace-shape warnings were detected.</p>"
    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(_string(warning)) for warning in warnings)


def _verify_rows(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<tr><td colspan=\"9\" class=\"muted\">No factual claims were extracted.</td></tr>"
    rows = []
    for claim in claims:
        root = claim.get("root_cause") or {}
        rows.append(
            """
            <tr>
              <td>{claim_id}</td>
              <td>{claim}</td>
              <td><span class="badge support-{support_class}">{support}</span></td>
              <td><span class="badge verdict-{verdict_class}">{verdict}</span></td>
              <td>{truth}</td>
              <td>{source}</td>
              <td>{citation}</td>
              <td>{context}</td>
              <td>{root}</td>
            </tr>
            """.format(
                claim_id=escape(_string(claim.get("claim_id"))),
                claim=escape(_string(claim.get("claim"))),
                support_class=escape(_css_token(claim.get("support_status"))),
                support=escape(_string(claim.get("support_status"))),
                verdict_class=escape(_css_token(claim.get("verdict"))),
                verdict=escape(_string(claim.get("verdict"))),
                truth=escape(_string(claim.get("truth_status"))),
                source=escape(_string(claim.get("source_status"))),
                citation=escape(_string(claim.get("citation_status"))),
                context=escape(_string(claim.get("best_context_id") or "none")),
                root=escape(_string(root.get("label") or "none")),
            )
        )
    return "\n".join(rows)


def _audit_rows(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<tr><td colspan=\"6\" class=\"muted\">Audit was not run. Pass --corpus to include corpus-level diagnosis.</td></tr>"
    rows = []
    for claim in claims:
        corpus = claim.get("corpus") or {}
        rows.append(
            """
            <tr>
              <td>{label}</td>
              <td>{stage}</td>
              <td>{claim}</td>
              <td>{corpus_doc}</td>
              <td>{summary}</td>
              <td>{fix}</td>
            </tr>
            """.format(
                label=escape(_string(claim.get("audit_label"))),
                stage=escape(_string(claim.get("failure_stage"))),
                claim=escape(_string(claim.get("claim"))),
                corpus_doc=escape(_string(corpus.get("best_document_id") or "none")),
                summary=escape(_string(claim.get("developer_summary"))),
                fix=escape(_string(claim.get("suggested_fix"))),
            )
        )
    return "\n".join(rows)


def _contexts(trace: RAGTrace) -> str:
    if not trace.contexts:
        return "<p class=\"muted\">No retrieved contexts were supplied.</p>"
    cards = []
    for index, context in enumerate(trace.contexts, start=1):
        cards.append(
            """
            <article class="item">
              <div class="item-meta">rank {rank} | {context_id}</div>
              <p>{text}</p>
            </article>
            """.format(
                rank=index,
                context_id=escape(context.id),
                text=escape(context.text),
            )
        )
    return "\n".join(cards)


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": result.get("summary"),
        "inspection": result.get("inspection"),
        "verification": {
            "summary": (result.get("verification") or {}).get("summary"),
            "abstention": (result.get("verification") or {}).get("abstention"),
        },
        "audit": {
            "summary": ((result.get("audit") or {}).get("summary") if result.get("audit") else None),
        },
        "next_actions": result.get("next_actions"),
    }


def _css_token(value: Any) -> str:
    token = _string(value).lower().replace("_", "-").replace(" ", "-")
    return "".join(char for char in token if char.isalnum() or char == "-") or "unknown"


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Evidence QA Report</title>
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
      grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
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
    .verdict-supported {{ color: var(--ok); background: #e9f7ef; }}
    .support-grounded-by-span {{ color: var(--ok); background: #e9f7ef; }}
    .support-grounded-without-span,
    .support-partially-grounded-by-span,
    .support-partially-grounded,
    .support-insufficient-evidence {{ color: var(--warn); background: #fff7df; }}
    .support-unsupported-by-retrieved-context,
    .support-contradicted-by-evidence {{ color: var(--bad); background: #fdeceb; }}
    .verdict-unsupported, .verdict-contradicted {{ color: var(--bad); background: #fdeceb; }}
    .verdict-partially-supported, .verdict-unverifiable {{ color: var(--warn); background: #fff7df; }}
    pre {{
      margin: 0;
      overflow: auto;
      background: #101828;
      color: #f8fafc;
      border-radius: 8px;
      padding: 14px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ContextTrace Evidence QA Report</h1>
      <p class="muted">Local end-to-end evidence QA: inspect, verify, audit, and risk summary.</p>
      <p class="muted">Grounded means supported by the selected evidence span. It does not mean independently true, current, or authoritative.</p>
    </header>

    <section>
      <h2>QA Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Prioritized Next Actions</h2>
      {next_actions}
    </section>

    <section>
      <h2>Risk Signals</h2>
      {risk_signals}
    </section>

    <section>
      <h2>Trace Shape Warnings</h2>
      {inspect_warnings}
    </section>

    <section>
      <h2>Query</h2>
      <p>{query}</p>
      <h2>Answer</h2>
      <p class="answer">{answer}</p>
    </section>

    <section>
      <h2>Claim Verification</h2>
      <table>
        <thead>
          <tr>
            <th>Claim ID</th>
            <th>Claim</th>
            <th>Support Status</th>
            <th>Verdict</th>
            <th>Truth</th>
            <th>Source</th>
            <th>Citation</th>
            <th>Best Context</th>
            <th>Root Cause</th>
          </tr>
        </thead>
        <tbody>{verify_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Retrieval And Corpus Audit</h2>
      <table>
        <thead>
          <tr>
            <th>Audit Label</th>
            <th>Stage</th>
            <th>Claim</th>
            <th>Corpus Document</th>
            <th>Developer Summary</th>
            <th>Suggested Fix</th>
          </tr>
        </thead>
        <tbody>{audit_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Retrieved Contexts</h2>
      {contexts}
    </section>

    <section>
      <h2>Raw JSON Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
