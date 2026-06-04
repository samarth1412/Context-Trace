from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


class CompareReportGenerator:
    def generate(self, result: dict[str, Any], *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any]) -> str:
        summary = result.get("summary") or {}
        changes = list(result.get("changes") or [])
        return HTML_TEMPLATE.format(
            verdict_class="bad" if summary.get("regression") else "ok",
            regression=escape(_string(summary.get("regression"))),
            mode=escape(_string(result.get("mode") or "lexical")),
            summary_cards=_summary_cards(summary),
            change_rows=_change_rows(changes),
            new_failures=_change_cards(
                changes,
                {"added_failure", "new_failure", "verdict_regressed", "citation_regressed", "root_cause_regressed"},
                empty="No new claim-level verification failures were detected.",
            ),
            resolved_failures=_change_cards(
                changes,
                {"resolved_failure", "removed_failure", "verdict_improved", "citation_improved"},
                empty="No previously failing claims were resolved.",
            ),
            root_changes=_root_changes(summary),
            baseline_summary=_run_summary(result.get("baseline") or {}),
            current_summary=_run_summary(result.get("current") or {}),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Regression", summary.get("regression")),
        ("Support Rate Delta", _signed(summary.get("support_rate_delta"))),
        ("Unsupported Rate Delta", _signed(summary.get("unsupported_claim_rate_delta"))),
        ("Citation Mismatch Delta", _signed(summary.get("citation_mismatch_delta"))),
        ("New Failures", summary.get("new_failures", 0)),
        ("Resolved Failures", summary.get("resolved_failures", 0)),
        ("New Unsupported", summary.get("new_unsupported", 0)),
        ("New Citation Mismatches", summary.get("new_citation_mismatches", 0)),
        ("Added Claims", summary.get("added_claims", 0)),
        ("Removed Claims", summary.get("removed_claims", 0)),
        ("Should Abstain Before", summary.get("should_abstain_before")),
        ("Should Abstain After", summary.get("should_abstain_after")),
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


def _change_rows(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "<tr><td colspan=\"7\" class=\"muted\">No claim-level changes detected.</td></tr>"
    rows = []
    for change in changes:
        before = change.get("before") or {}
        after = change.get("after") or {}
        rows.append(
            """
            <tr>
              <td><span class="badge status-{status_class}">{status}</span></td>
              <td>{claim}</td>
              <td>{before_verdict}</td>
              <td>{after_verdict}</td>
              <td>{before_root}</td>
              <td>{after_root}</td>
              <td>{fix}</td>
            </tr>
            """.format(
                status_class=escape(_css_token(change.get("status"))),
                status=escape(_string(change.get("status"))),
                claim=escape(_string(change.get("claim"))),
                before_verdict=escape(_string(before.get("verdict") or "none")),
                after_verdict=escape(_string(after.get("verdict") or "none")),
                before_root=escape(_string(before.get("root_cause") or "none")),
                after_root=escape(_string(after.get("root_cause") or "none")),
                fix=escape(_string(change.get("suggested_fix"))),
            )
        )
    return "\n".join(rows)


def _change_cards(changes: list[dict[str, Any]], statuses: set[str], *, empty: str) -> str:
    selected = [change for change in changes if change.get("status") in statuses]
    if not selected:
        return "<p class=\"muted\">%s</p>" % escape(empty)
    return "\n".join(_change_card(change) for change in selected)


def _change_card(change: dict[str, Any]) -> str:
    before = change.get("before") or {}
    after = change.get("after") or {}
    active = after or before
    return """
    <article class="item">
      <div class="item-meta">{status} | match {match_score}</div>
      <h3>{claim}</h3>
      <p><strong>Before:</strong> {before_verdict} | {before_citation} | {before_root}</p>
      <p><strong>After:</strong> {after_verdict} | {after_citation} | {after_root}</p>
      <p><strong>Best context:</strong> {context_id}</p>
      <p><strong>Closest evidence:</strong> {evidence}</p>
      <p><strong>Suggested fix:</strong> {fix}</p>
    </article>
    """.format(
        status=escape(_string(change.get("status"))),
        match_score=escape(_string(change.get("match_score") if change.get("match_score") is not None else "new")),
        claim=escape(_string(change.get("claim"))),
        before_verdict=escape(_string(before.get("verdict") or "none")),
        before_citation=escape(_string(before.get("citation_status") or "none")),
        before_root=escape(_string(before.get("root_cause") or "none")),
        after_verdict=escape(_string(after.get("verdict") or "none")),
        after_citation=escape(_string(after.get("citation_status") or "none")),
        after_root=escape(_string(after.get("root_cause") or "none")),
        context_id=escape(_string(active.get("best_context_id") or "none")),
        evidence=escape(_string(active.get("closest_evidence") or "none")),
        fix=escape(_string(change.get("suggested_fix"))),
    )


def _root_changes(summary: dict[str, Any]) -> str:
    new_roots = list(summary.get("new_root_causes") or [])
    resolved_roots = list(summary.get("resolved_root_causes") or [])
    if not new_roots and not resolved_roots:
        return "<p class=\"muted\">No root-cause labels changed.</p>"
    return """
    <div class="grid-two">
      <div class="item">
        <div class="item-meta">New root causes</div>
        <p>{new_roots}</p>
      </div>
      <div class="item">
        <div class="item-meta">Resolved root causes</div>
        <p>{resolved_roots}</p>
      </div>
    </div>
    """.format(
        new_roots=escape(", ".join(new_roots) or "none"),
        resolved_roots=escape(", ".join(resolved_roots) or "none"),
    )


def _run_summary(run: dict[str, Any]) -> str:
    summary = run.get("summary") or {}
    metadata = run.get("metadata") or {}
    cards = [
        ("Query", run.get("query")),
        ("Support Rate", summary.get("support_rate")),
        ("Unsupported Rate", summary.get("unsupported_claim_rate")),
        ("Citation Mismatches", summary.get("citation_mismatches")),
        ("Failure Type", summary.get("failure_type")),
        ("Primary Root Cause", summary.get("primary_root_cause")),
        ("Should Abstain", summary.get("should_abstain")),
        ("Input Type", metadata.get("compare_input_type")),
    ]
    return "\n".join(
        """
        <div class="card">
          <div class="label">{label}</div>
          <div class="small-value">{value}</div>
        </div>
        """.format(label=escape(label), value=escape(_string(value)))
        for label, value in cards
    )


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": result.get("mode"),
        "summary": result.get("summary"),
        "changes": result.get("changes"),
        "baseline": result.get("baseline"),
        "current": result.get("current"),
    }


def _signed(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number > 0:
        return "+%s" % _string(round(number, 3))
    return _string(round(number, 3))


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
  <title>ContextTrace Regression Report</title>
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
    .grid-two {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
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
    .small-value {{ margin-top: 4px; font-size: 14px; overflow-wrap: anywhere; }}
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
    .status-added-failure, .status-new-failure, .status-verdict-regressed,
    .status-citation-regressed, .status-root-cause-regressed {{ color: var(--bad); background: #fdeceb; }}
    .status-resolved-failure, .status-removed-failure, .status-verdict-improved,
    .status-citation-improved {{ color: var(--ok); background: #e9f7ef; }}
    .status-added-claim, .status-removed-claim, .status-source-changed,
    .status-claim-changed, .status-root-cause-changed {{ color: var(--warn); background: #fff7df; }}
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
      <h1>ContextTrace Regression Report</h1>
      <p class="muted">Local diff of two claim-level evidence verification runs.</p>
      <div class="banner {verdict_class}">
        <strong>Regression: {regression}</strong>
        <span class="muted"> | mode {mode}</span>
      </div>
    </header>

    <section>
      <h2>Regression Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Claim Changes</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Claim</th>
            <th>Before Verdict</th>
            <th>After Verdict</th>
            <th>Before Root Cause</th>
            <th>After Root Cause</th>
            <th>Suggested Fix</th>
          </tr>
        </thead>
        <tbody>{change_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>New Failures</h2>
      {new_failures}
    </section>

    <section>
      <h2>Resolved Failures</h2>
      {resolved_failures}
    </section>

    <section>
      <h2>Root Cause Changes</h2>
      {root_changes}
    </section>

    <section>
      <h2>Baseline Summary</h2>
      <div class="summary">{baseline_summary}</div>
    </section>

    <section>
      <h2>Current Summary</h2>
      <div class="summary">{current_summary}</div>
    </section>

    <section>
      <h2>Raw JSON Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
