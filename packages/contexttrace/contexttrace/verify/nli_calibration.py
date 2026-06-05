from __future__ import annotations

import json
import math
import time
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.benchmark import run_verify_benchmark
from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.local_nli import (
    DEFAULT_NLI_BACKEND,
    DEFAULT_NLI_MAX_LENGTH,
    LocalNLIError,
    build_nli_provider,
)


RISK_LABELS = {
    "citation_mismatch",
    "contradicted_answer",
    "partial_support",
    "should_have_abstained",
    "unsupported_answer",
}
UNSUPPORTED_LIKE_VERDICTS = {
    "contradicted",
    "partially_supported",
    "unsupported",
    "unverifiable",
}


class TimedNLIJudge:
    """Wrap a local NLI provider and record claim-level latency."""

    def __init__(self, nli: ClaimJudge) -> None:
        self.nli = nli
        self.call_latencies_ms: list[float] = []

    @property
    def provider(self) -> str:
        return str(getattr(self.nli, "provider", self.nli.__class__.__name__))

    @property
    def model(self) -> object:
        return getattr(self.nli, "model", None)

    def verify_claim(self, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return self.nli.verify_claim(**kwargs)
        finally:
            self.call_latencies_ms.append(round((time.perf_counter() - started) * 1000, 3))


def run_nli_calibration(
    *,
    nli: ClaimJudge | None = None,
    model_path: str | None = None,
    tokenizer_path: str | None = None,
    backend: str = DEFAULT_NLI_BACKEND,
    max_length: int = DEFAULT_NLI_MAX_LENGTH,
    case_set: str = "all",
    min_exact_match_rate: float = 0.8,
    min_entailment_precision: float = 0.85,
    min_contradiction_recall: float = 0.7,
    max_dangerous_miss_rate: float = 0.05,
    max_p95_latency_ms: float = 0.0,
) -> dict[str, Any]:
    provider = _resolve_nli_provider(
        nli=nli,
        model_path=model_path,
        tokenizer_path=tokenizer_path,
        backend=backend,
        max_length=max_length,
    )
    timed = TimedNLIJudge(provider)
    benchmark = run_verify_benchmark(
        mode="nli",
        case_set=case_set,
        nli=timed,
        time_cases=True,
    )
    rows = list(benchmark.get("rows") or [])
    scorecard = _scorecard(benchmark, rows, timed.call_latencies_ms)
    failures = nli_calibration_failures(
        scorecard,
        min_exact_match_rate=min_exact_match_rate,
        min_entailment_precision=min_entailment_precision,
        min_contradiction_recall=min_contradiction_recall,
        max_dangerous_miss_rate=max_dangerous_miss_rate,
        max_p95_latency_ms=max_p95_latency_ms,
    )
    dangerous_misses = _dangerous_misses(rows)
    unsupported_as_supported = _unsupported_as_supported_rows(rows)
    return {
        "status": "passed" if not failures else "failed",
        "case_set": benchmark.get("case_set"),
        "case_source": benchmark.get("case_source"),
        "cases": benchmark.get("cases"),
        "nli": _nli_metadata(provider),
        "thresholds": {
            "min_exact_match_rate": min_exact_match_rate,
            "min_entailment_precision": min_entailment_precision,
            "min_contradiction_recall": min_contradiction_recall,
            "max_dangerous_miss_rate": max_dangerous_miss_rate,
            "max_p95_latency_ms": max_p95_latency_ms,
        },
        "scorecard": scorecard,
        "failures": failures,
        "dangerous_miss_rows": _row_summaries(dangerous_misses),
        "unsupported_as_supported_rows": _row_summaries(unsupported_as_supported),
        "benchmark": benchmark,
    }


def nli_calibration_failures(
    scorecard: dict[str, Any],
    *,
    min_exact_match_rate: float,
    min_entailment_precision: float,
    min_contradiction_recall: float,
    max_dangerous_miss_rate: float,
    max_p95_latency_ms: float = 0.0,
) -> list[str]:
    failures = []
    if float(scorecard.get("exact_match_rate") or 0.0) < min_exact_match_rate:
        failures.append(
            "exact_match_rate %.3f < %.3f"
            % (float(scorecard.get("exact_match_rate") or 0.0), min_exact_match_rate)
        )
    if float(scorecard.get("entailment_precision") or 0.0) < min_entailment_precision:
        failures.append(
            "entailment_precision %.3f < %.3f"
            % (float(scorecard.get("entailment_precision") or 0.0), min_entailment_precision)
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
    if max_p95_latency_ms > 0 and float(scorecard.get("case_latency_p95_ms") or 0.0) > max_p95_latency_ms:
        failures.append(
            "case_latency_p95_ms %.3f > %.3f"
            % (float(scorecard.get("case_latency_p95_ms") or 0.0), max_p95_latency_ms)
        )
    return failures


def write_nli_calibration_report(result: dict[str, Any], *, path: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_nli_calibration_report(result), encoding="utf-8")
    return str(output_path)


def render_nli_calibration_report(result: dict[str, Any]) -> str:
    scorecard = result.get("scorecard") or {}
    misses = list(result.get("dangerous_miss_rows") or [])
    false_greens = list(result.get("unsupported_as_supported_rows") or [])
    return NLI_CALIBRATION_REPORT_TEMPLATE.format(
        status=escape(str(result.get("status") or "")),
        nli=escape(json.dumps(result.get("nli") or {}, sort_keys=True)),
        cases=escape(str(result.get("cases") or 0)),
        score_rows=_score_rows(scorecard),
        failures=_failure_list(result.get("failures") or []),
        dangerous_misses=_case_cards(misses, empty="No dangerous misses."),
        false_greens=_case_cards(false_greens, empty="No unsupported claims were over-marked as supported."),
        raw_json=escape(json.dumps(result, indent=2)),
    )


def _resolve_nli_provider(
    *,
    nli: ClaimJudge | None,
    model_path: str | None,
    tokenizer_path: str | None,
    backend: str,
    max_length: int,
) -> ClaimJudge:
    if nli is not None:
        return nli
    try:
        provider = build_nli_provider(
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            backend=backend,
            max_length=max_length,
        )
    except LocalNLIError as exc:
        raise ValueError(str(exc)) from exc
    if provider is None:
        raise ValueError(
            "nli-calibrate requires --model-path or CONTEXTTRACE_NLI_MODEL_PATH. "
            "ContextTrace never downloads NLI models automatically."
        )
    return provider


def _scorecard(
    benchmark: dict[str, Any],
    rows: list[dict[str, Any]],
    call_latencies_ms: list[float],
) -> dict[str, Any]:
    entailment = _verdict_metric(rows, "supported")
    contradiction = _verdict_metric(rows, "contradicted")
    unsupported_like = _combined_verdict_metric(rows, UNSUPPORTED_LIKE_VERDICTS)
    case_latencies = [
        float(row.get("latency_ms") or 0.0)
        for row in rows
        if "latency_ms" in row
    ]
    dangerous_rows = [
        row for row in rows if set(row.get("expected") or []) & RISK_LABELS
    ]
    dangerous_misses = _dangerous_misses(rows)
    unsupported_as_supported = _unsupported_as_supported_rows(rows)
    return {
        "exact_match_rate": float(benchmark.get("exact_match_rate") or 0.0),
        "verdict_match_rate": float(benchmark.get("verdict_match_rate") or 0.0),
        "citation_match_rate": float(benchmark.get("citation_match_rate") or 0.0),
        "abstention_match_rate": float(benchmark.get("abstention_match_rate") or 0.0),
        "entailment_precision": entailment["precision"],
        "entailment_recall": entailment["recall"],
        "contradiction_precision": contradiction["precision"],
        "contradiction_recall": contradiction["recall"],
        "unsupported_like_recall": unsupported_like["recall"],
        "dangerous_miss_rate": round(len(dangerous_misses) / len(dangerous_rows), 3) if dangerous_rows else 0.0,
        "dangerous_misses": len(dangerous_misses),
        "dangerous_cases": len(dangerous_rows),
        "unsupported_as_supported_cases": len(unsupported_as_supported),
        "case_latency_avg_ms": _average(case_latencies),
        "case_latency_p50_ms": _percentile(case_latencies, 50),
        "case_latency_p95_ms": _percentile(case_latencies, 95),
        "case_latency_total_ms": round(sum(case_latencies), 3),
        "nli_call_count": len(call_latencies_ms),
        "nli_call_latency_avg_ms": _average(call_latencies_ms),
        "nli_call_latency_p50_ms": _percentile(call_latencies_ms, 50),
        "nli_call_latency_p95_ms": _percentile(call_latencies_ms, 95),
    }


def _verdict_metric(rows: list[dict[str, Any]], verdict: str) -> dict[str, float]:
    return _combined_verdict_metric(rows, {verdict})


def _combined_verdict_metric(rows: list[dict[str, Any]], verdicts: set[str]) -> dict[str, float]:
    tp = fp = fn = 0
    for row in rows:
        expected = row.get("expected_verdict_counts") or {}
        predicted = row.get("predicted_verdict_counts") or {}
        expected_count = sum(int(expected.get(verdict) or 0) for verdict in verdicts)
        predicted_count = sum(int(predicted.get(verdict) or 0) for verdict in verdicts)
        tp += min(expected_count, predicted_count)
        fp += max(0, predicted_count - expected_count)
        fn += max(0, expected_count - predicted_count)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }


def _dangerous_misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if set(row.get("expected") or []) & RISK_LABELS
        and set(row.get("predicted") or []) == {"no_failure_detected"}
    ]


def _unsupported_as_supported_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flagged = []
    for row in rows:
        expected = row.get("expected_verdict_counts") or {}
        predicted = row.get("predicted_verdict_counts") or {}
        expected_unsupported_like = sum(int(expected.get(verdict) or 0) for verdict in UNSUPPORTED_LIKE_VERDICTS)
        expected_supported = int(expected.get("supported") or 0)
        predicted_supported = int(predicted.get("supported") or 0)
        if expected_unsupported_like > 0 and predicted_supported > expected_supported:
            flagged.append(row)
    return flagged


def _row_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": row.get("id"),
            "expected": row.get("expected"),
            "predicted": row.get("predicted"),
            "expected_verdict_counts": row.get("expected_verdict_counts"),
            "predicted_verdict_counts": row.get("predicted_verdict_counts"),
            "latency_ms": row.get("latency_ms"),
            "note": row.get("note"),
        }
        for row in rows
    ]


def _nli_metadata(nli: ClaimJudge) -> dict[str, Any]:
    return {
        "provider": str(getattr(nli, "provider", nli.__class__.__name__)),
        "model": getattr(nli, "model", None),
        "backend": getattr(nli, "backend", None),
        "model_path": getattr(nli, "model_path", None),
        "tokenizer_path": getattr(nli, "tokenizer_path", None),
        "max_length": getattr(nli, "max_length", None),
    }


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ranked = sorted(float(value) for value in values)
    index = max(0, min(len(ranked) - 1, math.ceil((percentile / 100) * len(ranked)) - 1))
    return round(ranked[index], 3)


def _score_rows(scorecard: dict[str, Any]) -> str:
    return "\n".join(
        "<tr><td>{key}</td><td>{value}</td></tr>".format(
            key=escape(str(key)),
            value=escape(str(value)),
        )
        for key, value in scorecard.items()
    )


def _failure_list(failures: list[str]) -> str:
    if not failures:
        return "<p class=\"ok\">All calibration gates passed.</p>"
    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(str(item)) for item in failures)


def _case_cards(rows: list[dict[str, Any]], *, empty: str) -> str:
    if not rows:
        return "<p class=\"ok\">%s</p>" % escape(empty)
    return "\n".join(
        """
        <article class="item">
          <div class="item-meta">{case_id}</div>
          <p><strong>Expected:</strong> {expected}</p>
          <p><strong>Predicted:</strong> {predicted}</p>
          <p><strong>Expected verdicts:</strong> {expected_verdicts}</p>
          <p><strong>Predicted verdicts:</strong> {predicted_verdicts}</p>
          <p><strong>Latency:</strong> {latency_ms} ms</p>
          <p>{note}</p>
        </article>
        """.format(
            case_id=escape(str(row.get("id"))),
            expected=escape(", ".join(row.get("expected") or [])),
            predicted=escape(", ".join(row.get("predicted") or [])),
            expected_verdicts=escape(json.dumps(row.get("expected_verdict_counts") or {}, sort_keys=True)),
            predicted_verdicts=escape(json.dumps(row.get("predicted_verdict_counts") or {}, sort_keys=True)),
            latency_ms=escape(str(row.get("latency_ms") or 0)),
            note=escape(str(row.get("note") or "")),
        )
        for row in rows
    )


NLI_CALIBRATION_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Local NLI Calibration</title>
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
      <h1>ContextTrace Local NLI Calibration</h1>
      <p class="muted">Status: <strong>{status}</strong>. NLI: {nli}. Cases: {cases}.</p>
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
      <h2>Unsupported Marked Supported</h2>
      {false_greens}
    </section>
    <section>
      <h2>Raw JSON</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
