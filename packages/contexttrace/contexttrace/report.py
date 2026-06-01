from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Iterable

from contexttrace.reliability import ReliabilityScorer


class ReportGenerator:
    def generate(self, trace: dict[str, Any], *, path: str = "report.html") -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(trace), encoding="utf-8")
        return str(output_path)

    def generate_eval_report(
        self,
        eval_run: dict[str, Any],
        traces: Iterable[dict[str, Any]],
        *,
        path: str,
    ) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render_eval_report(eval_run, traces), encoding="utf-8")
        return str(output_path)

    def render_eval_report(self, eval_run: dict[str, Any], traces: Iterable[dict[str, Any]]) -> str:
        trace_list = list(traces)
        summary = eval_run.get("summary") or {}
        failure_counts: dict[str, int] = {}
        trace_rows = []
        for trace in trace_list:
            evaluation = trace.get("evaluation") or {}
            failure = evaluation.get("failure") or {}
            scores = evaluation.get("scores") or {}
            failure_type = failure.get("failure_type") or "not_evaluated"
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
            trace_rows.append(
                """
                <tr>
                  <td>{trace_id}</td>
                  <td>{query}</td>
                  <td>{failure}</td>
                  <td>{citation_support}</td>
                  <td>{unsupported}</td>
                </tr>
                """.format(
                    trace_id=escape(_string(trace.get("id"))),
                    query=escape(_string(trace.get("query"))[:160]),
                    failure=escape(_string(failure_type)),
                    citation_support=escape(_string(scores.get("citation_support", ""))),
                    unsupported=escape(_string(scores.get("unsupported_claim_rate", ""))),
                )
            )
        return EVAL_HTML_TEMPLATE.format(
            dataset=escape(_string(eval_run.get("dataset"))),
            endpoint=escape(_string(eval_run.get("endpoint"))),
            eval_run_id=escape(_string(eval_run.get("id"))),
            summary=_render_kv(summary),
            failure_breakdown=_render_kv(failure_counts),
            traces="\n".join(trace_rows)
            or "<tr><td colspan=\"5\" class=\"muted\">No traces were recorded.</td></tr>",
        )

    def render(self, trace: dict[str, Any]) -> str:
        answer = trace.get("answer") or {}
        metadata = trace.get("metadata") or {}
        answer_metadata = answer.get("metadata") or {}
        chunks = trace.get("chunks") or []
        selected_chunks = [chunk for chunk in chunks if chunk.get("selected")]
        citation_checks = _citation_checks(trace)
        evaluation = trace.get("evaluation") or {}
        failure = evaluation.get("failure") or {}
        scores = evaluation.get("scores") or _score_summary(citation_checks)
        reliability = (
            evaluation.get("reliability")
            if isinstance(evaluation.get("reliability"), dict)
            else ReliabilityScorer().score_trace(trace).to_dict()
        )
        usage = answer.get("usage") or {}
        latency = _first_present(
            metadata,
            answer_metadata,
            keys=(
                "latency_ms",
                "latency_seconds",
                "total_latency_ms",
                "generation_latency_ms",
            ),
        )

        return HTML_TEMPLATE.format(
            title=escape("ContextTrace Report"),
            query=escape(_string(trace.get("query"))),
            answer=escape(_string(answer.get("answer"))),
            generated_at=escape(_string(trace.get("updated_at") or trace.get("created_at"))),
            token_usage=_render_kv(usage) if usage else "<p class=\"muted\">No token usage logged.</p>",
            latency=escape(_string(latency)) if latency is not None else "Not logged",
            reliability_score=escape(_string(reliability.get("score", 0))),
            reliability_grade=escape(_string(reliability.get("grade", "F"))),
            reliability_strengths=_render_list(reliability.get("strengths") or []),
            reliability_weaknesses=_render_list(reliability.get("weaknesses") or []),
            reliability_recommendations=_render_list(reliability.get("recommendations") or []),
            reliability_components=_render_kv(reliability.get("components") or {}),
            reliability_scores=_render_kv(scores) if scores else "<p class=\"muted\">No raw scores available.</p>",
            retrieved_chunks=_render_chunks(chunks),
            selected_context=_render_chunks(selected_chunks),
            citation_checks=_render_citation_checks(citation_checks),
            failure_type=escape(_string(failure.get("failure_type") or "not_evaluated")),
            severity=escape(_string(failure.get("severity") or "unknown")),
            root_cause=escape(_string(failure.get("root_cause") or "No failure analysis available.")),
            suggested_fix=escape(_string(failure.get("suggested_fix") or "Run trace.evaluate() before exporting.")),
        )


def _citation_checks(trace: dict[str, Any]) -> list[dict[str, Any]]:
    evaluation_checks = (trace.get("evaluation") or {}).get("citation_checks") or []
    if evaluation_checks:
        return list(evaluation_checks)
    return list(trace.get("citation_checks") or [])


def _render_chunks(chunks: Iterable[dict[str, Any]]) -> str:
    items = []
    for chunk in chunks:
        score = chunk.get("relevance_score")
        score_text = "" if score is None else " | score %s" % escape(_string(score))
        source = chunk.get("source") or "unknown source"
        selected = " | selected" if chunk.get("selected") else ""
        items.append(
            """
            <article class="item">
              <div class="item-meta">{chunk_id} | {source}{score}{selected}</div>
              <p>{content}</p>
            </article>
            """.format(
                chunk_id=escape(_string(chunk.get("chunk_id") or chunk.get("id") or "chunk")),
                source=escape(_string(source)),
                score=score_text,
                selected=selected,
                content=escape(_string(chunk.get("content"))),
            )
        )
    if not items:
        return "<p class=\"muted\">No chunks logged.</p>"
    return "\n".join(items)


def _render_citation_checks(checks: Iterable[dict[str, Any]]) -> str:
    rows = []
    for check in checks:
        verdict = check.get("verdict") or check.get("support_status") or "pending"
        reason = check.get("reason") or check.get("rationale") or ""
        score = check.get("support_score")
        rows.append(
            """
            <tr>
              <td>{claim}</td>
              <td>{source_chunk_id}</td>
              <td><span class="badge verdict-{verdict_class}">{verdict}</span></td>
              <td>{score}</td>
              <td>{reason}</td>
            </tr>
            """.format(
                claim=escape(_string(check.get("claim"))),
                source_chunk_id=escape(_string(check.get("source_chunk_id"))),
                verdict=escape(_string(verdict)),
                verdict_class=escape(_string(verdict).replace("_", "-")),
                score=escape(_string(score if score is not None else "")),
                reason=escape(_string(reason)),
            )
        )
    if not rows:
        return "<p class=\"muted\">No citation checks logged.</p>"

    return """
    <table>
      <thead>
        <tr>
          <th>Claim</th>
          <th>Source Chunk</th>
          <th>Support Verdict</th>
          <th>Score</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """.format(rows="\n".join(rows))


def _render_kv(values: dict[str, Any]) -> str:
    rows = []
    for key, value in values.items():
        rows.append(
            "<div><dt>{key}</dt><dd>{value}</dd></div>".format(
                key=escape(_string(key).replace("_", " ").title()),
                value=escape(_string(value)),
            )
        )
    return "<dl class=\"metrics\">%s</dl>" % "\n".join(rows)


def _render_list(values: Iterable[Any]) -> str:
    items = ["<li>%s</li>" % escape(_string(value)) for value in values]
    if not items:
        return "<p class=\"muted\">None recorded.</p>"
    return "<ul>%s</ul>" % "\n".join(items)


def _score_summary(checks: list[dict[str, Any]]) -> dict[str, float]:
    if not checks:
        return {}
    support_scores = [float(check.get("support_score") or 0.0) for check in checks]
    unsupported = [
        check
        for check in checks
        if (check.get("verdict") or check.get("support_status"))
        in {"unsupported", "contradicted", "not_enough_info"}
    ]
    return {
        "citation_support": round(sum(support_scores) / len(support_scores), 3),
        "unsupported_claim_rate": round(len(unsupported) / len(checks), 3),
    }


def _first_present(*dicts: dict[str, Any], keys: Iterable[str]) -> Any:
    for values in dicts:
        for key in keys:
            if key in values and values[key] is not None:
                return values[key]
    return None


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #697386;
      --line: #d8dee8;
      --accent: #2458d3;
      --ok: #176f44;
      --warn: #946200;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 24px;
      padding-bottom: 18px;
    }}
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
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-top: 18px;
    }}
    .summary > div, .item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }}
    .label, .item-meta, dt {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .02em;
      text-transform: uppercase;
    }}
    .value {{
      font-size: 17px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}
    .answer {{
      white-space: pre-wrap;
      font-size: 15px;
    }}
    .item + .item {{ margin-top: 10px; }}
    .item p {{ margin: 8px 0 0; white-space: pre-wrap; }}
    .muted {{ color: var(--muted); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      background: #eef2f7;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .verdict-directly-supported {{ color: var(--ok); background: #e9f7ef; }}
    .verdict-partially-supported, .verdict-not-enough-info {{ color: var(--warn); background: #fff7df; }}
    .verdict-unsupported, .verdict-contradicted {{ color: var(--bad); background: #fdeceb; }}
    .metrics {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      margin: 0;
    }}
    .metrics div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfe;
    }}
    dd {{ margin: 4px 0 0; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ContextTrace Report</h1>
      <p class="muted">Generated from trace data {generated_at}</p>
      <div class="summary">
        <div>
          <div class="label">Reliability Score</div>
          <div class="value">{reliability_score} ({reliability_grade})</div>
        </div>
        <div>
          <div class="label">Failure Type</div>
          <div class="value">{failure_type}</div>
        </div>
        <div>
          <div class="label">Severity</div>
          <div class="value">{severity}</div>
        </div>
        <div>
          <div class="label">Latency</div>
          <div class="value">{latency}</div>
        </div>
      </div>
    </header>

    <section>
      <h2>Reliability Score</h2>
      <p class="muted">A practical diagnostic score for comparing traces. It summarizes available metrics but does not replace the raw measurements below.</p>
      <div class="grid">
        <div>
          <h3>Strengths</h3>
          {reliability_strengths}
        </div>
        <div>
          <h3>Weaknesses</h3>
          {reliability_weaknesses}
        </div>
        <div>
          <h3>Recommendations</h3>
          {reliability_recommendations}
        </div>
      </div>
      <h3>Component Scores</h3>
      {reliability_components}
      <h3>Raw Metrics</h3>
      {reliability_scores}
    </section>

    <section>
      <h2>Query</h2>
      <p>{query}</p>
    </section>

    <section>
      <h2>Answer</h2>
      <p class="answer">{answer}</p>
    </section>

    <section>
      <h2>Token Usage</h2>
      {token_usage}
    </section>

    <section>
      <h2>Failure Analysis</h2>
      <div class="grid">
        <div>
          <h3>Root Cause</h3>
          <p>{root_cause}</p>
        </div>
        <div>
          <h3>Suggested Fix</h3>
          <p>{suggested_fix}</p>
        </div>
      </div>
    </section>

    <section>
      <h2>Citation Checks</h2>
      {citation_checks}
    </section>

    <section>
      <h2>Selected Context</h2>
      {selected_context}
    </section>

    <section>
      <h2>Retrieved Chunks</h2>
      {retrieved_chunks}
    </section>
  </main>
</body>
</html>
"""


EVAL_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Eval Report</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #697386;
      --line: #d8dee8;
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
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 1px solid var(--line); margin-bottom: 24px; padding-bottom: 18px; }}
    h1 {{ margin: 0; font-size: 30px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }}
    .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .metrics {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      margin: 0;
    }}
    .metrics div {{ border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fbfcfe; }}
    dt {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    dd {{ margin: 4px 0 0; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ContextTrace Eval Report</h1>
      <p class="muted">Eval run {eval_run_id}</p>
      <p><strong>Dataset:</strong> {dataset}<br><strong>Endpoint:</strong> {endpoint}</p>
    </header>
    <section>
      <h2>Executive Summary</h2>
      {summary}
    </section>
    <section>
      <h2>Failure Breakdown</h2>
      {failure_breakdown}
    </section>
    <section>
      <h2>Trace Details</h2>
      <table>
        <thead>
          <tr>
            <th>Trace ID</th>
            <th>Query</th>
            <th>Failure Type</th>
            <th>Citation Support</th>
            <th>Unsupported Claim Rate</th>
          </tr>
        </thead>
        <tbody>{traces}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
