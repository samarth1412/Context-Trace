from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


class SuiteReportGenerator:
    def generate(self, result: dict[str, Any], *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any]) -> str:
        summary = result.get("summary") or {}
        cases = list(result.get("cases") or [])
        return HTML_TEMPLATE.format(
            suite_name=escape(_string(result.get("suite_name"))),
            mode=escape(_string(result.get("mode") or "lexical")),
            status_class="bad" if summary.get("status") == "failed" else "ok",
            status=escape(_string(summary.get("status"))),
            summary_cards=_summary_cards(summary),
            case_rows=_case_rows(cases),
            failed_cases=_case_cards(
                [case for case in cases if case.get("status") in {"failed", "error"}],
                empty="No suite cases failed.",
            ),
            resolved_cases=_case_cards(
                [
                    case
                    for case in cases
                    if int((((case.get("comparison") or {}).get("summary") or {}).get("resolved_failures") or 0)) > 0
                ],
                empty="No previously failing claims were resolved in this run.",
            ),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Status", summary.get("status")),
        ("Cases", summary.get("total_cases")),
        ("Passed", summary.get("passed")),
        ("Failed", summary.get("failed")),
        ("Errors", summary.get("errors")),
        ("Regressions", summary.get("regressions")),
        ("Resolved Failures", summary.get("resolved_failures")),
        ("New Failures", summary.get("new_failures")),
        ("Average Support Rate", summary.get("average_support_rate")),
        ("Pass Risk Cases", summary.get("pass_risk_cases")),
        ("Medium Risk Cases", summary.get("medium_risk_cases")),
        ("High Risk Cases", summary.get("high_risk_cases")),
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


def _case_rows(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "<tr><td colspan=\"8\" class=\"muted\">No suite cases were run.</td></tr>"
    rows = []
    for case in cases:
        current = case.get("current") or {}
        current_summary = current.get("summary") or {}
        comparison_summary = ((case.get("comparison") or {}).get("summary") or {})
        rows.append(
            """
            <tr>
              <td><span class="badge status-{status_class}">{status}</span></td>
              <td>{case_id}</td>
              <td>{query}</td>
              <td>{risk}</td>
              <td>{support_rate}</td>
              <td>{primary_issue}</td>
              <td>{regression}</td>
              <td>{resolved}</td>
            </tr>
            """.format(
                status_class=escape(_css_token(case.get("status"))),
                status=escape(_string(case.get("status"))),
                case_id=escape(_string(case.get("id"))),
                query=escape(_string(case.get("query"))),
                risk=escape(_string(current_summary.get("risk_level") or "unknown")),
                support_rate=escape(_string(current_summary.get("support_rate"))),
                primary_issue=escape(_string(current_summary.get("primary_issue") or "unknown")),
                regression=escape(_string(comparison_summary.get("regression"))),
                resolved=escape(_string(comparison_summary.get("resolved_failures") or 0)),
            )
        )
    return "\n".join(rows)


def _case_cards(cases: list[dict[str, Any]], *, empty: str) -> str:
    if not cases:
        return "<p class=\"muted\">%s</p>" % escape(empty)
    return "\n".join(_case_card(case) for case in cases)


def _case_card(case: dict[str, Any]) -> str:
    current = case.get("current") or {}
    current_summary = current.get("summary") or {}
    comparison_summary = ((case.get("comparison") or {}).get("summary") or {})
    failures = list(case.get("failures") or [])
    actions = list(case.get("next_actions") or current.get("next_actions") or [])
    return """
    <article class="item">
      <div class="item-meta">{case_id} | {status}</div>
      <h3>{query}</h3>
      <p><strong>Risk:</strong> {risk} | <strong>Primary issue:</strong> {issue} | <strong>Support rate:</strong> {support_rate}</p>
      <p><strong>Regression:</strong> {regression} | <strong>Resolved failures:</strong> {resolved} | <strong>New failures:</strong> {new_failures}</p>
      <p><strong>Failures:</strong> {failures}</p>
      <p><strong>Next actions:</strong> {actions}</p>
    </article>
    """.format(
        case_id=escape(_string(case.get("id"))),
        status=escape(_string(case.get("status"))),
        query=escape(_string(case.get("query"))),
        risk=escape(_string(current_summary.get("risk_level") or "unknown")),
        issue=escape(_string(current_summary.get("primary_issue") or "unknown")),
        support_rate=escape(_string(current_summary.get("support_rate"))),
        regression=escape(_string(comparison_summary.get("regression"))),
        resolved=escape(_string(comparison_summary.get("resolved_failures") or 0)),
        new_failures=escape(_string(comparison_summary.get("new_failures") or 0)),
        failures=escape("; ".join(_string(item) for item in failures) or "none"),
        actions=escape("; ".join(_string(item) for item in actions[:3]) or "none"),
    )


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_name": result.get("suite_name"),
        "mode": result.get("mode"),
        "summary": result.get("summary"),
        "cases": [
            {
                "id": case.get("id"),
                "status": case.get("status"),
                "failures": case.get("failures"),
                "current_summary": ((case.get("current") or {}).get("summary") or {}),
                "comparison_summary": ((case.get("comparison") or {}).get("summary") or {}),
            }
            for case in result.get("cases") or []
        ],
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
  <title>ContextTrace Regression Suite Report</title>
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
    .banner {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--subtle);
      padding: 14px;
      margin-top: 12px;
    }}
    .banner.ok {{ border-color: #a7dfbf; background: #edf9f1; }}
    .banner.bad {{ border-color: #f3b1ac; background: #fff1f0; }}
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
    .status-passed {{ color: var(--ok); background: #e9f7ef; }}
    .status-failed, .status-error {{ color: var(--bad); background: #fdeceb; }}
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
      <h1>ContextTrace Regression Suite Report</h1>
      <p class="muted">Replay saved RAG failures and guardrails against a live endpoint.</p>
      <div class="banner {status_class}">
        <strong>{suite_name}: {status}</strong>
        <span class="muted"> | mode {mode}</span>
      </div>
    </header>

    <section>
      <h2>Suite Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Case Results</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Case</th>
            <th>Query</th>
            <th>Risk</th>
            <th>Support Rate</th>
            <th>Primary Issue</th>
            <th>Regression</th>
            <th>Resolved</th>
          </tr>
        </thead>
        <tbody>{case_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Failed Cases</h2>
      {failed_cases}
    </section>

    <section>
      <h2>Resolved Failures</h2>
      {resolved_cases}
    </section>

    <section>
      <h2>Raw JSON Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
