from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


class DiagnoseReportGenerator:
    def generate(self, result: dict[str, Any], *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any]) -> str:
        summary = result.get("summary") or {}
        agent = result.get("agent") or {}
        rag = result.get("rag") or {}
        return HTML_TEMPLATE.format(
            status=escape(_string(summary.get("status"))),
            trace_type=escape(_string(result.get("trace_type"))),
            primary_issue=escape(_string(summary.get("primary_issue"))),
            suggested_fix=escape(_string(summary.get("suggested_fix"))),
            cards=_summary_cards(summary),
            findings=_finding_cards(result.get("findings") or []),
            agent_events=_agent_events(agent.get("events") or []),
            rag_claims=_rag_claims(rag.get("claims") or []),
            next_actions=_next_actions(result.get("next_actions") or []),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2, sort_keys=True)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Status", summary.get("status")),
        ("Trace Type", summary.get("trace_type")),
        ("Primary Issue", summary.get("primary_issue")),
        ("Findings", summary.get("total_findings")),
        ("High Risk", summary.get("high_risk_findings")),
        ("Agent Findings", summary.get("agent_findings")),
        ("RAG Failure", summary.get("rag_failure_type")),
        ("RAG Support Rate", summary.get("rag_support_rate")),
        ("Negative Tool Results", summary.get("agent_negative_tool_results")),
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


def _finding_cards(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "<p class=\"muted\">No diagnosis findings.</p>"
    return "\n".join(
        """
        <article class="item severity-{severity}">
          <div class="item-meta">{finding_id} | {source} | {severity}</div>
          <h3>{finding_type}</h3>
          <p>{reason}</p>
          <p><strong>Tool:</strong> {tool}</p>
          <p><strong>Evidence:</strong> {evidence}</p>
          <p><strong>Suggested fix:</strong> {fix}</p>
        </article>
        """.format(
            finding_id=escape(_string(item.get("id"))),
            source=escape(_string(item.get("source"))),
            severity=escape(_string(item.get("severity"))),
            finding_type=escape(_string(item.get("type"))),
            reason=escape(_string(item.get("reason"))),
            tool=escape(_string(item.get("tool") or "n/a")),
            evidence=escape(_string(item.get("evidence") or "n/a")),
            fix=escape(_string(item.get("suggested_fix"))),
        )
        for item in findings
    )


def _agent_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "<p class=\"muted\">No agent steps or events were supplied.</p>"
    rows = []
    for event in events:
        rows.append(
            """
            <tr>
              <td>{index}</td>
              <td>{event_type}</td>
              <td>{name}</td>
              <td><pre>{input_json}</pre></td>
              <td><pre>{output_json}</pre></td>
              <td>{error}</td>
            </tr>
            """.format(
                index=escape(_string(event.get("index"))),
                event_type=escape(_string(event.get("event_type"))),
                name=escape(_string(event.get("name"))),
                input_json=escape(_json(event.get("input_json"))),
                output_json=escape(_json(event.get("output_json"))),
                error=escape(_string(event.get("error_message"))),
            )
        )
    return """
    <table>
      <thead><tr><th>#</th><th>Type</th><th>Name</th><th>Input</th><th>Output</th><th>Error</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """.format(rows="\n".join(rows))


def _rag_claims(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<p class=\"muted\">No RAG claim verification was run.</p>"
    rows = []
    for claim in claims:
        rows.append(
            """
            <tr>
              <td>{claim_id}</td>
              <td>{claim}</td>
              <td>{verdict}</td>
              <td>{context_id}</td>
              <td>{root}</td>
            </tr>
            """.format(
                claim_id=escape(_string(claim.get("claim_id"))),
                claim=escape(_string(claim.get("claim"))),
                verdict=escape(_string(claim.get("verdict"))),
                context_id=escape(_string(claim.get("best_context_id"))),
                root=escape(_string((claim.get("root_cause") or {}).get("label"))),
            )
        )
    return """
    <table>
      <thead><tr><th>ID</th><th>Claim</th><th>Verdict</th><th>Best Context</th><th>Root Cause</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """.format(rows="\n".join(rows))


def _next_actions(actions: list[Any]) -> str:
    if not actions:
        return "<p class=\"muted\">No next actions.</p>"
    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(_string(action)) for action in actions)


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_path": result.get("trace_path"),
        "trace_type": result.get("trace_type"),
        "summary": result.get("summary"),
        "findings": result.get("findings"),
        "next_actions": result.get("next_actions"),
    }


def _json(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, sort_keys=True)
    except TypeError:
        return _string(value)


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Diagnosis Report</title>
  <style>
    :root {{
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
    .severity-high {{ border-color: #f3b4af; background: #fff7f6; }}
    .severity-medium {{ border-color: #f2d28a; background: #fffaf0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    pre {{
      margin: 0;
      overflow: auto;
      white-space: pre-wrap;
      background: #101828;
      color: #f8fafc;
      border-radius: 8px;
      padding: 10px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ContextTrace Diagnosis Report</h1>
      <p class="muted">Local-first failure localization for RAG and agent traces.</p>
      <p><strong>{status}</strong> | {trace_type} | {primary_issue}</p>
    </header>

    <section>
      <h2>Summary</h2>
      <div class="summary">{cards}</div>
    </section>

    <section>
      <h2>Primary Fix</h2>
      <p>{suggested_fix}</p>
    </section>

    <section>
      <h2>Findings</h2>
      {findings}
    </section>

    <section>
      <h2>Agent Timeline</h2>
      {agent_events}
    </section>

    <section>
      <h2>RAG Claims</h2>
      {rag_claims}
    </section>

    <section>
      <h2>Next Actions</h2>
      {next_actions}
    </section>

    <section>
      <h2>Raw JSON Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
