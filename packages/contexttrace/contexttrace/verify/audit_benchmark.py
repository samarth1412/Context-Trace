from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.audit import audit_trace_with_corpus
from contexttrace.verify.schema import RAGTrace, TraceContext, load_trace


AUDIT_BENCHMARK_CASE_FILES = {
    "real": (
        Path(__file__).with_name("audit_benchmark_cases.json"),
        "real OSS RAG docs, public GitHub issue snippets, and ContextTrace docs",
    ),
}


@dataclass(frozen=True)
class AuditBenchmarkCase:
    id: str
    trace: RAGTrace
    corpus_contexts: list[TraceContext]
    expected_label: str
    source: str
    note: str


def audit_benchmark_cases(*, case_set: str = "real") -> list[AuditBenchmarkCase]:
    return [_case(item) for item in _case_items(case_set)]


def run_audit_benchmark(*, mode: str = "lexical", case_set: str = "real") -> dict[str, Any]:
    rows = []
    labels = set()
    for case in audit_benchmark_cases(case_set=case_set):
        result = audit_trace_with_corpus(
            case.trace,
            case.corpus_contexts,
            corpus_path=case.source,
            mode=mode,
        )
        predicted = str((result.get("summary") or {}).get("primary_audit_label") or "no_failure_detected")
        expected = case.expected_label
        labels.add(expected)
        labels.add(predicted)
        rows.append(
            {
                "id": case.id,
                "source": case.source,
                "note": case.note,
                "expected": expected,
                "predicted": predicted,
                "exact_match": expected == predicted,
                "summary": result.get("summary") or {},
                "claims": result.get("claims") or [],
                "verification": result.get("verification") or {},
                "corpus": result.get("corpus") or {},
            }
        )

    per_label = {}
    for label in sorted(labels):
        tp = sum(1 for row in rows if row["expected"] == label and row["predicted"] == label)
        fp = sum(1 for row in rows if row["expected"] != label and row["predicted"] == label)
        fn = sum(1 for row in rows if row["expected"] == label and row["predicted"] != label)
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
        "per_label": per_label,
        "rows": rows,
    }


def write_audit_benchmark_report(result: dict[str, Any], *, path: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_audit_benchmark_report(result), encoding="utf-8")
    return str(output_path)


def render_audit_benchmark_report(result: dict[str, Any]) -> str:
    rows = list(result.get("rows") or [])
    misses = [row for row in rows if not row.get("exact_match")]
    return AUDIT_BENCHMARK_REPORT_TEMPLATE.format(
        mode=escape(str(result.get("mode") or "")),
        source=escape(str(result.get("case_source") or "")),
        summary_cards=_summary_cards(result),
        label_rows=_label_rows(result.get("per_label") or {}),
        case_rows=_case_rows(rows),
        misses=_misses(misses),
        raw_json=escape(json.dumps(result, indent=2)),
    )


def _case(item: dict[str, Any]) -> AuditBenchmarkCase:
    trace = load_trace(
        {
            "query": item["query"],
            "answer": item["answer"],
            "contexts": item.get("retrieved_contexts") or [],
            "citations": item.get("citations") or [],
            "metadata": {
                "audit_benchmark_case_id": item["id"],
                "audit_benchmark_source": item.get("source", ""),
                "real_benchmark": True,
            },
        },
        source="real audit benchmark case %s" % item["id"],
    )
    corpus_contexts = [
        TraceContext(
            id=str(context["id"]),
            text=str(context["text"]),
            metadata=_context_metadata(context),
        )
        for context in item.get("corpus_contexts") or []
    ]
    return AuditBenchmarkCase(
        id=str(item["id"]),
        trace=trace,
        corpus_contexts=corpus_contexts,
        expected_label=str(item["expected_label"]),
        source=str(item.get("source") or ""),
        note=str(item.get("note") or ""),
    )


def _case_items(case_set: str) -> list[dict[str, Any]]:
    normalized = _normalize_case_set(case_set)
    path, _ = AUDIT_BENCHMARK_CASE_FILES[normalized]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def _normalize_case_set(case_set: str) -> str:
    normalized = str(case_set or "real").strip().lower()
    if normalized not in AUDIT_BENCHMARK_CASE_FILES:
        raise ValueError(
            "Audit benchmark case set must be one of: %s."
            % ", ".join(AUDIT_BENCHMARK_CASE_FILES)
        )
    return normalized


def _case_source(case_set: str) -> str:
    normalized = _normalize_case_set(case_set)
    return AUDIT_BENCHMARK_CASE_FILES[normalized][1]


def _context_metadata(context: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in context.items()
        if key not in {"id", "text"}
    }
    metadata["real_document"] = True
    return metadata


def _summary_cards(result: dict[str, Any]) -> str:
    cards = [
        ("Cases", result.get("cases", 0)),
        ("Exact Match", result.get("exact_match_rate", 0)),
        ("Case Source", result.get("case_set", "")),
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
        status = "pass" if row.get("exact_match") else "fail"
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
                expected=escape(str(row.get("expected"))),
                predicted=escape(str(row.get("predicted"))),
                note=escape(str(row.get("note") or "")),
            )
        )
    return "\n".join(output)


def _misses(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">No misses across audit labels.</p>"
    cards = []
    for row in rows:
        claims = []
        for claim in row.get("claims") or []:
            retrieved = claim.get("retrieved") or {}
            corpus = claim.get("corpus") or {}
            claims.append(
                """
                <li>
                  <strong>{audit_label}</strong> {claim}<br>
                  <span class="muted">Reason: {reason}</span><br>
                  <span class="muted">Retrieved: {retrieved}</span><br>
                  <span class="muted">Corpus: {corpus}</span>
                </li>
                """.format(
                    audit_label=escape(str(claim.get("audit_label"))),
                    claim=escape(str(claim.get("claim"))),
                    reason=escape(str(claim.get("reason"))),
                    retrieved=escape(str(retrieved.get("evidence") or "none")),
                    corpus=escape(str(corpus.get("evidence") or "none")),
                )
            )
        cards.append(
            """
            <article class="item">
              <div class="item-meta">{case_id} | {source}</div>
              <p><strong>Expected:</strong> {expected}</p>
              <p><strong>Predicted:</strong> {predicted}</p>
              <ul>{claims}</ul>
            </article>
            """.format(
                case_id=escape(str(row.get("id"))),
                source=escape(str(row.get("source"))),
                expected=escape(str(row.get("expected"))),
                predicted=escape(str(row.get("predicted"))),
                claims="\n".join(claims),
            )
        )
    return "\n".join(cards)


AUDIT_BENCHMARK_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ContextTrace Audit Benchmark</title>
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
      <h1>ContextTrace Audit Benchmark</h1>
      <p class="muted">Mode: {mode}. Cases use {source}.</p>
    </header>

    <section>
      <h2>Usefulness Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Audit Label Metrics</h2>
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
