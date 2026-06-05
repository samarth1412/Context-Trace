from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, load_trace


BENCHMARK_CASE_FILES = {
    "contexttrace": (
        Path(__file__).with_name("real_benchmark_cases.json"),
        "real ContextTrace repository docs and release artifacts",
    ),
    "external": (
        Path(__file__).with_name("external_benchmark_cases.json"),
        "real external OSS docs and public GitHub issues",
    ),
}


@dataclass(frozen=True)
class VerifyBenchmarkCase:
    id: str
    trace: RAGTrace
    expected_labels: set[str]
    expected_verdict_counts: dict[str, int]
    expected_citation_statuses: list[str]
    expected_should_abstain: bool | None
    source: str
    note: str


def benchmark_cases(*, case_set: str = "contexttrace") -> list[VerifyBenchmarkCase]:
    return [
        _case(item)
        for item in _case_items(case_set)
    ]


def run_verify_benchmark(
    *,
    mode: str = "lexical",
    case_set: str = "contexttrace",
    judge: ClaimJudge | None = None,
) -> dict[str, Any]:
    rows = []
    labels = set()
    verdict_names = {"supported", "partially_supported", "unsupported", "contradicted", "unverifiable"}
    verdict_correct = 0
    citation_correct = 0
    citation_expected = 0
    abstention_correct = 0
    abstention_expected = 0

    for case in benchmark_cases(case_set=case_set):
        result = verify_trace(case.trace, mode=mode, judge=judge)
        predicted = _predicted_labels(result)
        expected_verdict_counts = dict(case.expected_verdict_counts)
        predicted_verdict_counts = {
            verdict: int((result.get("summary") or {}).get(verdict) or 0)
            for verdict in verdict_names
        }
        expected_citations = list(case.expected_citation_statuses)
        predicted_citations = [
            str(claim.get("citation_status"))
            for claim in result.get("claims") or []
            if claim.get("citation_status")
        ]
        expected_abstain = case.expected_should_abstain
        predicted_abstain = bool((result.get("abstention") or {}).get("should_abstain"))

        labels.update(case.expected_labels)
        labels.update(predicted)

        verdict_match = _counts_match(expected_verdict_counts, predicted_verdict_counts)
        if verdict_match:
            verdict_correct += 1
        if expected_citations:
            citation_expected += 1
            if expected_citations == predicted_citations:
                citation_correct += 1
        if expected_abstain is not None:
            abstention_expected += 1
            if expected_abstain == predicted_abstain:
                abstention_correct += 1

        labels_match = predicted == case.expected_labels
        rows.append(
            {
                "id": case.id,
                "source": case.source,
                "note": case.note,
                "expected": sorted(case.expected_labels),
                "predicted": sorted(predicted),
                "exact_match": labels_match,
                "expected_verdict_counts": expected_verdict_counts,
                "predicted_verdict_counts": {
                    key: value for key, value in sorted(predicted_verdict_counts.items())
                },
                "verdict_match": verdict_match,
                "expected_citation_statuses": expected_citations,
                "predicted_citation_statuses": predicted_citations,
                "citation_match": (expected_citations == predicted_citations) if expected_citations else None,
                "expected_should_abstain": expected_abstain,
                "predicted_should_abstain": predicted_abstain,
                "abstention_match": (expected_abstain == predicted_abstain) if expected_abstain is not None else None,
                "summary": result.get("summary") or {},
                "claims": result.get("claims") or [],
                "abstention": result.get("abstention") or {},
            }
        )

    per_label = {}
    for label in sorted(labels):
        tp = sum(1 for row in rows if label in row["expected"] and label in row["predicted"])
        fp = sum(1 for row in rows if label not in row["expected"] and label in row["predicted"])
        fn = sum(1 for row in rows if label in row["expected"] and label not in row["predicted"])
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_label[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    exact_matches = sum(1 for row in rows if row["exact_match"])
    return {
        "mode": mode,
        "case_set": _normalize_case_set(case_set),
        "case_source": _case_source(case_set),
        "cases": len(rows),
        "exact_match_rate": round(exact_matches / len(rows), 3) if rows else 0.0,
        "verdict_match_rate": round(verdict_correct / len(rows), 3) if rows else 0.0,
        "citation_match_rate": round(citation_correct / citation_expected, 3) if citation_expected else 1.0,
        "abstention_match_rate": round(abstention_correct / abstention_expected, 3) if abstention_expected else 1.0,
        "per_label": per_label,
        "rows": rows,
    }


def write_verify_benchmark_report(result: dict[str, Any], *, path: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_verify_benchmark_report(result), encoding="utf-8")
    return str(output_path)


def render_verify_benchmark_report(result: dict[str, Any]) -> str:
    rows = list(result.get("rows") or [])
    misses = [row for row in rows if not _row_passed(row)]
    return BENCHMARK_REPORT_TEMPLATE.format(
        mode=escape(str(result.get("mode") or "")),
        source=escape(str(result.get("case_source") or "")),
        summary_cards=_summary_cards(result),
        label_rows=_label_rows(result.get("per_label") or {}),
        case_rows=_case_rows(rows),
        misses=_misses(misses),
        raw_json=escape(json.dumps(result, indent=2)),
    )


def _case(item: dict[str, Any]) -> VerifyBenchmarkCase:
    contexts = [
        {
            "id": context["id"],
            "text": context["text"],
            "metadata": _context_metadata(context),
        }
        for context in item.get("contexts") or []
    ]
    trace = load_trace(
        {
            "query": item["query"],
            "answer": item["answer"],
            "contexts": contexts,
            "citations": item.get("citations") or [],
            "metadata": {
                "benchmark_case_id": item["id"],
                "benchmark_source": item.get("source", ""),
                "real_benchmark": True,
            },
        },
        source="real verify benchmark case %s" % item["id"],
    )
    return VerifyBenchmarkCase(
        id=str(item["id"]),
        trace=trace,
        expected_labels=set(item.get("expected_labels") or []),
        expected_verdict_counts=dict(item.get("expected_verdict_counts") or {}),
        expected_citation_statuses=list(item.get("expected_citation_statuses") or []),
        expected_should_abstain=item.get("expected_should_abstain"),
        source=str(item.get("source") or ""),
        note=str(item.get("note") or ""),
    )


def _case_items(case_set: str) -> list[dict[str, Any]]:
    normalized = _normalize_case_set(case_set)
    names = list(BENCHMARK_CASE_FILES) if normalized == "all" else [normalized]
    items: list[dict[str, Any]] = []
    for name in names:
        path, _ = BENCHMARK_CASE_FILES[name]
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.extend(payload["cases"])
    return items


def _normalize_case_set(case_set: str) -> str:
    normalized = str(case_set or "contexttrace").strip().lower()
    if normalized not in {*BENCHMARK_CASE_FILES.keys(), "all"}:
        raise ValueError(
            "Benchmark case set must be one of: %s."
            % ", ".join([*BENCHMARK_CASE_FILES.keys(), "all"])
        )
    return normalized


def _case_source(case_set: str) -> str:
    normalized = _normalize_case_set(case_set)
    if normalized == "all":
        return "real ContextTrace repository docs plus external OSS docs and public GitHub issues"
    return BENCHMARK_CASE_FILES[normalized][1]


def _context_metadata(context: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in context.items()
        if key not in {"id", "text"}
    }
    metadata["real_document"] = True
    return metadata


def _predicted_labels(result: dict[str, Any]) -> set[str]:
    labels = set((result.get("summary") or {}).get("failure_types") or [])
    return labels or {"no_failure_detected"}


def _counts_match(expected: dict[str, int], predicted: dict[str, int]) -> bool:
    for key, value in expected.items():
        if int(predicted.get(key) or 0) != int(value):
            return False
    return True


def _row_passed(row: dict[str, Any]) -> bool:
    checks = [
        bool(row.get("exact_match")),
        bool(row.get("verdict_match")),
    ]
    if row.get("citation_match") is not None:
        checks.append(bool(row.get("citation_match")))
    if row.get("abstention_match") is not None:
        checks.append(bool(row.get("abstention_match")))
    return all(checks)


def _summary_cards(result: dict[str, Any]) -> str:
    cards = [
        ("Cases", result.get("cases", 0)),
        ("Failure Label Exact Match", result.get("exact_match_rate", 0)),
        ("Verdict Match", result.get("verdict_match_rate", 0)),
        ("Citation Match", result.get("citation_match_rate", 0)),
        ("Abstention Match", result.get("abstention_match_rate", 0)),
    ]
    return "\n".join(
        """
        <div class="card">
          <div class="label">{label}</div>
          <div class="value">{value}</div>
        </div>
        """.format(label=escape(str(label)), value=escape(str(value)))
        for label, value in cards
    )


def _label_rows(per_label: dict[str, Any]) -> str:
    if not per_label:
        return "<tr><td colspan=\"7\" class=\"muted\">No label metrics.</td></tr>"
    rows = []
    for label, metrics in sorted(per_label.items()):
        rows.append(
            """
            <tr>
              <td>{label}</td>
              <td>{precision}</td>
              <td>{recall}</td>
              <td>{f1}</td>
              <td>{tp}</td>
              <td>{fp}</td>
              <td>{fn}</td>
            </tr>
            """.format(
                label=escape(str(label)),
                precision=escape(str(metrics.get("precision"))),
                recall=escape(str(metrics.get("recall"))),
                f1=escape(str(metrics.get("f1"))),
                tp=escape(str(metrics.get("tp"))),
                fp=escape(str(metrics.get("fp"))),
                fn=escape(str(metrics.get("fn"))),
            )
        )
    return "\n".join(rows)


def _case_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan=\"6\" class=\"muted\">No benchmark cases.</td></tr>"
    output = []
    for row in rows:
        status = "pass" if _row_passed(row) else "fail"
        output.append(
            """
            <tr>
              <td><span class="badge {status}">{status}</span></td>
              <td>{case_id}</td>
              <td>{source}</td>
              <td>{expected}</td>
              <td>{predicted}</td>
              <td>{note}</td>
            </tr>
            """.format(
                status=escape(status),
                case_id=escape(str(row.get("id"))),
                source=escape(str(row.get("source"))),
                expected=escape(", ".join(row.get("expected") or [])),
                predicted=escape(", ".join(row.get("predicted") or [])),
                note=escape(str(row.get("note") or "")),
            )
        )
    return "\n".join(output)


def _misses(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            "<p class=\"muted\">No misses across failure labels, verdict counts, citations, or abstention. "
            "Matched facts and Missing facts are available in the raw JSON.</p>"
        )
    cards = []
    for row in rows:
        claim_bits = []
        for claim in row.get("claims") or []:
            claim_bits.append(
                """
                <li>
                  <strong>{verdict}</strong> {claim}<br>
                  <span class="muted">{reason}</span><br>
                  <span class="muted">Matched facts: {matched_facts}</span><br>
                  <span class="muted">Missing facts: {missing_facts}</span><br>
                  <span class="muted">Supporting spans: {supporting_spans}</span><br>
                  <span class="muted">Root cause: {root_cause}</span>
                </li>
                """.format(
                    verdict=escape(str(claim.get("verdict"))),
                    claim=escape(str(claim.get("claim"))),
                    reason=escape(str(claim.get("reason"))),
                    matched_facts=escape(_fact_summary(claim.get("matched_fact_details") or claim.get("matched_facts") or [])),
                    missing_facts=escape(_fact_summary(claim.get("missing_fact_details") or claim.get("missing_facts") or [])),
                    supporting_spans=escape(_span_summary(claim.get("supporting_spans") or [])),
                    root_cause=escape(_root_summary(claim.get("root_cause") or {})),
                )
            )
        cards.append(
            """
            <article class="item">
              <div class="item-meta">{case_id} | {source}</div>
              <p><strong>Expected labels:</strong> {expected}</p>
              <p><strong>Predicted labels:</strong> {predicted}</p>
              <p><strong>Expected verdict counts:</strong> {expected_counts}</p>
              <p><strong>Predicted verdict counts:</strong> {predicted_counts}</p>
              <p><strong>Expected abstain:</strong> {expected_abstain} | <strong>Predicted abstain:</strong> {predicted_abstain}</p>
              <ul>{claims}</ul>
            </article>
            """.format(
                case_id=escape(str(row.get("id"))),
                source=escape(str(row.get("source"))),
                expected=escape(", ".join(row.get("expected") or [])),
                predicted=escape(", ".join(row.get("predicted") or [])),
                expected_counts=escape(json.dumps(row.get("expected_verdict_counts") or {}, sort_keys=True)),
                predicted_counts=escape(json.dumps(row.get("predicted_verdict_counts") or {}, sort_keys=True)),
                expected_abstain=escape(str(row.get("expected_should_abstain"))),
                predicted_abstain=escape(str(row.get("predicted_should_abstain"))),
                claims="\n".join(claim_bits),
            )
        )
    return "\n".join(cards)


def _fact_summary(facts: list[Any]) -> str:
    values = []
    for fact in facts:
        if isinstance(fact, dict):
            text = str(fact.get("text") or "")
            fact_type = str(fact.get("type") or "")
            values.append("%s (%s)" % (text, fact_type) if fact_type else text)
        else:
            values.append(str(fact))
    return ", ".join(value for value in values if value) or "none"


def _span_summary(spans: list[Any]) -> str:
    values = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        values.append(
            "%s %s score %s"
            % (
                span.get("context_id") or "",
                span.get("span_hash") or "",
                span.get("score") or "",
            )
        )
    return ", ".join(value.strip() for value in values if value.strip()) or "none"


def _root_summary(root_cause: dict[str, Any]) -> str:
    if not isinstance(root_cause, dict):
        return "none"
    label = str(root_cause.get("label") or "")
    missing_fact = str(root_cause.get("missing_fact") or "")
    if label and missing_fact:
        return "%s; missing=%s" % (label, missing_fact)
    return label or "none"


BENCHMARK_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Verification Benchmark</title>
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
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
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
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
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
    .value {{ margin-top: 4px; font-size: 20px; overflow-wrap: anywhere; }}
    .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .pass {{ color: var(--ok); background: #e9f7ef; }}
    .fail {{ color: var(--bad); background: #fdeceb; }}
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
      <h1>ContextTrace Verification Benchmark</h1>
      <p class="muted">Mode: {mode}. Cases use {source}.</p>
    </header>

    <section>
      <h2>Usefulness Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Failure Label Metrics</h2>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1</th>
            <th>TP</th>
            <th>FP</th>
            <th>FN</th>
          </tr>
        </thead>
        <tbody>{label_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Case Results</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Case</th>
            <th>Source</th>
            <th>Expected</th>
            <th>Predicted</th>
            <th>Why This Case Exists</th>
          </tr>
        </thead>
        <tbody>{case_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Misses To Inspect</h2>
      {misses}
    </section>

    <section>
      <h2>Raw JSON</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""
