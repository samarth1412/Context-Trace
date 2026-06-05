from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.benchmark import run_verify_benchmark
from contexttrace.verify.judges import ClaimJudge


RISK_LABELS = {
    "citation_mismatch",
    "contradicted_answer",
    "partial_support",
    "should_have_abstained",
    "unsupported_answer",
}


def run_judge_calibration(
    *,
    judge: ClaimJudge,
    case_set: str = "all",
    min_exact_match_rate: float = 0.85,
    min_contradiction_recall: float = 0.8,
    max_dangerous_miss_rate: float = 0.05,
) -> dict[str, Any]:
    benchmark = run_verify_benchmark(mode="judge", case_set=case_set, judge=judge)
    rows = list(benchmark.get("rows") or [])
    dangerous_rows = [
        row
        for row in rows
        if set(row.get("expected") or []) & RISK_LABELS
    ]
    dangerous_misses = [
        row
        for row in dangerous_rows
        if set(row.get("predicted") or []) == {"no_failure_detected"}
    ]
    per_label = benchmark.get("per_label") or {}
    contradiction_recall = _metric(per_label, "contradicted_answer", "recall")
    citation_mismatch_recall = _metric(per_label, "citation_mismatch", "recall")
    unsupported_recall = _metric(per_label, "unsupported_answer", "recall")
    abstention_recall = _metric(per_label, "should_have_abstained", "recall")
    dangerous_miss_rate = (
        len(dangerous_misses) / len(dangerous_rows)
        if dangerous_rows
        else 0.0
    )
    scorecard = {
        "exact_match_rate": float(benchmark.get("exact_match_rate") or 0.0),
        "verdict_match_rate": float(benchmark.get("verdict_match_rate") or 0.0),
        "citation_match_rate": float(benchmark.get("citation_match_rate") or 0.0),
        "abstention_match_rate": float(benchmark.get("abstention_match_rate") or 0.0),
        "contradiction_recall": contradiction_recall,
        "citation_mismatch_recall": citation_mismatch_recall,
        "unsupported_recall": unsupported_recall,
        "abstention_recall": abstention_recall,
        "dangerous_miss_rate": round(dangerous_miss_rate, 3),
        "dangerous_misses": len(dangerous_misses),
        "dangerous_cases": len(dangerous_rows),
    }
    failures = calibration_failures(
        scorecard,
        min_exact_match_rate=min_exact_match_rate,
        min_contradiction_recall=min_contradiction_recall,
        max_dangerous_miss_rate=max_dangerous_miss_rate,
    )
    return {
        "status": "passed" if not failures else "failed",
        "case_set": benchmark.get("case_set"),
        "case_source": benchmark.get("case_source"),
        "cases": benchmark.get("cases"),
        "judge": _judge_metadata(judge),
        "thresholds": {
            "min_exact_match_rate": min_exact_match_rate,
            "min_contradiction_recall": min_contradiction_recall,
            "max_dangerous_miss_rate": max_dangerous_miss_rate,
        },
        "scorecard": scorecard,
        "failures": failures,
        "dangerous_miss_rows": [
            {
                "id": row.get("id"),
                "expected": row.get("expected"),
                "predicted": row.get("predicted"),
                "note": row.get("note"),
            }
            for row in dangerous_misses
        ],
        "benchmark": benchmark,
    }


def calibration_failures(
    scorecard: dict[str, Any],
    *,
    min_exact_match_rate: float,
    min_contradiction_recall: float,
    max_dangerous_miss_rate: float,
) -> list[str]:
    failures = []
    if float(scorecard.get("exact_match_rate") or 0.0) < min_exact_match_rate:
        failures.append(
            "exact_match_rate %.3f < %.3f"
            % (float(scorecard.get("exact_match_rate") or 0.0), min_exact_match_rate)
        )
    if float(scorecard.get("contradiction_recall") or 0.0) < min_contradiction_recall:
        failures.append(
            "contradiction_recall %.3f < %.3f"
            % (float(scorecard.get("contradiction_recall") or 0.0), min_contradiction_recall)
        )
    if float(scorecard.get("dangerous_miss_rate") or 0.0) > max_dangerous_miss_rate:
        failures.append(
            "dangerous_miss_rate %.3f > %.3f"
            % (float(scorecard.get("dangerous_miss_rate") or 0.0), max_dangerous_miss_rate)
        )
    return failures


def write_judge_calibration_report(result: dict[str, Any], *, path: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_judge_calibration_report(result), encoding="utf-8")
    return str(output_path)


def render_judge_calibration_report(result: dict[str, Any]) -> str:
    scorecard = result.get("scorecard") or {}
    misses = result.get("dangerous_miss_rows") or []
    return CALIBRATION_REPORT_TEMPLATE.format(
        status=escape(str(result.get("status") or "")),
        judge=escape(json.dumps(result.get("judge") or {}, sort_keys=True)),
        cases=escape(str(result.get("cases") or 0)),
        score_rows=_score_rows(scorecard),
        failures=_failure_list(result.get("failures") or []),
        dangerous_misses=_dangerous_misses(misses),
        raw_json=escape(json.dumps(result, indent=2)),
    )


def _metric(per_label: dict[str, Any], label: str, metric: str) -> float:
    return float((per_label.get(label) or {}).get(metric) or 0.0)


def _judge_metadata(judge: ClaimJudge) -> dict[str, Any]:
    metadata = {
        "provider": str(getattr(judge, "provider", judge.__class__.__name__)),
        "model": getattr(judge, "model", None),
    }
    stats = getattr(judge, "stats", None)
    if callable(stats):
        metadata["cache"] = stats()
    return metadata


def _score_rows(scorecard: dict[str, Any]) -> str:
    rows = []
    for key, value in scorecard.items():
        rows.append(
            "<tr><td>{key}</td><td>{value}</td></tr>".format(
                key=escape(str(key)),
                value=escape(str(value)),
            )
        )
    return "\n".join(rows)


def _failure_list(failures: list[str]) -> str:
    if not failures:
        return "<p class=\"ok\">All calibration gates passed.</p>"
    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(str(item)) for item in failures)


def _dangerous_misses(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"ok\">No dangerous misses.</p>"
    return "\n".join(
        """
        <article class="item">
          <div class="item-meta">{case_id}</div>
          <p><strong>Expected:</strong> {expected}</p>
          <p><strong>Predicted:</strong> {predicted}</p>
          <p>{note}</p>
        </article>
        """.format(
            case_id=escape(str(row.get("id"))),
            expected=escape(", ".join(row.get("expected") or [])),
            predicted=escape(", ".join(row.get("predicted") or [])),
            note=escape(str(row.get("note") or "")),
        )
        for row in rows
    )


CALIBRATION_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Judge Calibration</title>
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
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 1px solid var(--line); margin-bottom: 22px; padding-bottom: 18px; }}
    h1, h2 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .muted, .item-meta {{ color: var(--muted); }}
    .ok {{ color: var(--ok); font-weight: 700; }}
    .bad {{ color: var(--bad); font-weight: 700; }}
    .item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--subtle);
      padding: 12px;
      margin-top: 10px;
    }}
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
      <h1>ContextTrace Judge Calibration</h1>
      <p class="muted">Status: <strong>{status}</strong>. Judge: {judge}. Cases: {cases}.</p>
    </header>
    <section>
      <h2>Scorecard</h2>
      <table><tbody>{score_rows}</tbody></table>
    </section>
    <section>
      <h2>Calibration Gates</h2>
      {failures}
    </section>
    <section>
      <h2>Dangerous Misses</h2>
      {dangerous_misses}
    </section>
    <section>
      <h2>Raw JSON</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
