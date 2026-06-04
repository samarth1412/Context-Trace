from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace


class AuditReportGenerator:
    def generate(self, result: dict[str, Any], trace: RAGTrace, *, path: str) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(result, trace), encoding="utf-8")
        return str(output_path)

    def render(self, result: dict[str, Any], trace: RAGTrace) -> str:
        summary = result.get("summary") or {}
        claims = list(result.get("claims") or [])
        return HTML_TEMPLATE.format(
            query=escape(_string(result.get("query"))),
            answer=escape(_string(result.get("answer"))),
            summary_cards=_summary_cards(summary),
            next_actions=_next_actions(summary),
            claim_rows=_claim_rows(claims),
            retrieval_misses=_claim_cards(claims, {"retrieval_miss"}, "No retrieval misses detected."),
            chunking_issues=_claim_cards(
                claims,
                {"chunking_issue", "reranking_failure"},
                "No chunking or reranking failures detected.",
            ),
            corpus_gaps=_claim_cards(claims, {"corpus_gap"}, "No corpus coverage gaps detected."),
            answer_overreach=_claim_cards(
                claims,
                {"answer_overreach", "insufficient_context", "stale_source"},
                "No answer overreach, stale source, or insufficient-context failures detected.",
            ),
            retrieved_contexts=_retrieved_contexts(trace),
            corpus_summary=escape(json.dumps(result.get("corpus") or {}, indent=2)),
            why_failed=_why_failed(claims),
            raw_json=escape(json.dumps(_raw_summary(result), indent=2)),
        )


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Primary Audit Label", summary.get("primary_audit_label")),
        ("Total Claims", summary.get("total_claims", 0)),
        ("Audited Failures", summary.get("audited_claims", 0)),
        ("Corpus Documents", summary.get("corpus_documents", 0)),
        ("Retrieval Changes", summary.get("retrieval_change_claims", 0)),
        ("Generation Changes", summary.get("generation_change_claims", 0)),
        ("Corpus Changes", summary.get("corpus_change_claims", 0)),
        ("Citation Changes", summary.get("citation_change_claims", 0)),
        ("Retrieval Misses", summary.get("retrieval_miss", 0)),
        ("Chunking Issues", summary.get("chunking_issue", 0)),
        ("Reranking Failures", summary.get("reranking_failure", 0)),
        ("Corpus Gaps", summary.get("corpus_gap", 0)),
        ("Answer Overreach", summary.get("answer_overreach", 0)),
        ("Stale Sources", summary.get("stale_source", 0)),
        ("Insufficient Context", summary.get("insufficient_context", 0)),
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


def _next_actions(summary: dict[str, Any]) -> str:
    actions = list(summary.get("top_recommended_actions") or [])
    if not actions:
        return "<p class=\"muted\">No audit-level action is needed for this trace.</p>"
    items = []
    for action in actions:
        items.append(
            "<li><strong>{count} claim(s):</strong> {action}</li>".format(
                count=escape(_string(action.get("claims"))),
                action=escape(_string(action.get("action"))),
            )
        )
    return "<ul>%s</ul>" % "\n".join(items)


def _claim_rows(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "<tr><td colspan=\"8\" class=\"muted\">No factual claims were extracted.</td></tr>"
    rows = []
    for claim in claims:
        retrieved = claim.get("retrieved") or {}
        corpus = claim.get("corpus") or {}
        label = _string(claim.get("audit_label"))
        rows.append(
            """
            <tr>
              <td><span class="badge audit-{label_class}">{label}</span></td>
              <td>{stage}</td>
              <td>{claim}</td>
              <td>{retrieved_verdict}</td>
              <td>{retrieved_context}</td>
              <td>{corpus_verdict}</td>
              <td>{corpus_document}</td>
              <td>{fix}</td>
            </tr>
            """.format(
                label_class=escape(_css_token(label)),
                label=escape(label),
                stage=escape(_string(claim.get("failure_stage"))),
                claim=escape(_string(claim.get("claim"))),
                retrieved_verdict=escape(_string(retrieved.get("verdict"))),
                retrieved_context=escape(_string(retrieved.get("best_context_id") or "none")),
                corpus_verdict=escape(_string(corpus.get("verdict"))),
                corpus_document=escape(_string(corpus.get("best_document_id") or "none")),
                fix=escape(_string(claim.get("suggested_fix"))),
            )
        )
    return "\n".join(rows)


def _claim_cards(claims: list[dict[str, Any]], labels: set[str], empty: str) -> str:
    selected = [claim for claim in claims if claim.get("audit_label") in labels]
    if not selected:
        return "<p class=\"muted\">%s</p>" % escape(empty)
    return "\n".join(_claim_card(claim) for claim in selected)


def _claim_card(claim: dict[str, Any]) -> str:
    retrieved = claim.get("retrieved") or {}
    corpus = claim.get("corpus") or {}
    return """
    <article class="item">
      <div class="item-meta">{claim_id} | {label} | confidence {confidence}</div>
      <h3>{claim}</h3>
      <p><strong>Diagnosis:</strong> {reason}</p>
      <p><strong>Failure stage:</strong> {stage} | <strong>Evidence status:</strong> {evidence_status}</p>
      <p><strong>Retrieved evidence:</strong> {retrieved_evidence}</p>
      <p class="muted">Retrieved context: {retrieved_context} | verdict {retrieved_verdict} | score {retrieved_score}</p>
      <p><strong>Corpus evidence:</strong> {corpus_evidence}</p>
      <p class="muted">Corpus document: {corpus_document} | verdict {corpus_verdict} | score {corpus_score}</p>
      <p><strong>Developer summary:</strong> {developer_summary}</p>
      <p><strong>Suggested fix:</strong> {fix}</p>
      {actions}
    </article>
    """.format(
        claim_id=escape(_string(claim.get("claim_id"))),
        label=escape(_string(claim.get("audit_label"))),
        confidence=escape(_string(claim.get("confidence"))),
        claim=escape(_string(claim.get("claim"))),
        reason=escape(_string(claim.get("reason"))),
        stage=escape(_string(claim.get("failure_stage"))),
        evidence_status=escape(_string(claim.get("evidence_status"))),
        retrieved_evidence=escape(_string(retrieved.get("evidence") or "none")),
        retrieved_context=escape(_string(retrieved.get("best_context_id") or "none")),
        retrieved_verdict=escape(_string(retrieved.get("verdict"))),
        retrieved_score=escape(_string(retrieved.get("best_score"))),
        corpus_evidence=escape(_string(corpus.get("evidence") or "none")),
        corpus_document=escape(_string(corpus.get("best_document_id") or "none")),
        corpus_verdict=escape(_string(corpus.get("verdict"))),
        corpus_score=escape(_string(corpus.get("best_score"))),
        developer_summary=escape(_string(claim.get("developer_summary"))),
        fix=escape(_string(claim.get("suggested_fix"))),
        actions=_action_list(claim.get("recommended_actions") or []),
    )


def _action_list(actions: list[str]) -> str:
    if not actions:
        return ""
    return "<p><strong>Recommended actions:</strong></p><ul>%s</ul>" % "\n".join(
        "<li>%s</li>" % escape(_string(action)) for action in actions
    )


def _retrieved_contexts(trace: RAGTrace) -> str:
    if not trace.contexts:
        return "<p class=\"muted\">No retrieved contexts were supplied.</p>"
    cards = []
    for index, context in enumerate(trace.contexts, start=1):
        cards.append(
            """
            <article class="item">
              <div class="item-meta">rank {rank} | {context_id} | {metadata}</div>
              <p>{text}</p>
            </article>
            """.format(
                rank=index,
                context_id=escape(context.id),
                metadata=escape(json.dumps(context.metadata, sort_keys=True) if context.metadata else "no metadata"),
                text=escape(context.text),
            )
        )
    return "\n".join(cards)


def _why_failed(claims: list[dict[str, Any]]) -> str:
    explanations = []
    for claim in claims:
        label = _string(claim.get("audit_label"))
        if label == "no_failure_detected":
            continue
        explanations.append(
            "%s: %s Suggested fix: %s"
            % (
                label,
                _string(claim.get("reason")),
                _string(claim.get("suggested_fix")),
            )
        )
    if not explanations:
        explanations.append("No corpus-level evidence-chain failure was detected.")
    return "<ul>%s</ul>" % "\n".join("<li>%s</li>" % escape(item) for item in explanations)


def _raw_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": result.get("summary"),
        "claims": result.get("claims"),
        "verification": result.get("verification"),
        "corpus": result.get("corpus"),
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
  <title>ContextTrace Retrieval Audit Report</title>
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
    .audit-no-failure-detected {{ color: var(--ok); background: #e9f7ef; }}
    .audit-retrieval-miss, .audit-corpus-gap, .audit-stale-source {{ color: var(--bad); background: #fdeceb; }}
    .audit-chunking-issue, .audit-reranking-failure,
    .audit-answer-overreach, .audit-insufficient-context {{ color: var(--warn); background: #fff7df; }}
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
      <h1>ContextTrace Retrieval Audit Report</h1>
      <p class="muted">Local corpus-level diagnosis for claim evidence failures.</p>
    </header>

    <section>
      <h2>Audit Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Prioritized Next Actions</h2>
      {next_actions}
    </section>

    <section>
      <h2>Query</h2>
      <p>{query}</p>
      <h2>Answer</h2>
      <p class="answer">{answer}</p>
    </section>

    <section>
      <h2>Claim Failure Diagnosis</h2>
      <table>
        <thead>
          <tr>
            <th>Audit Label</th>
            <th>Stage</th>
            <th>Claim</th>
            <th>Retrieved Verdict</th>
            <th>Retrieved Context</th>
            <th>Corpus Verdict</th>
            <th>Corpus Document</th>
            <th>Suggested Fix</th>
          </tr>
        </thead>
        <tbody>{claim_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Retrieval Misses</h2>
      {retrieval_misses}
    </section>

    <section>
      <h2>Chunking And Reranking Issues</h2>
      {chunking_issues}
    </section>

    <section>
      <h2>Corpus Gaps</h2>
      {corpus_gaps}
    </section>

    <section>
      <h2>Answer Overreach And Ambiguous Evidence</h2>
      {answer_overreach}
    </section>

    <section>
      <h2>Retrieved Contexts</h2>
      {retrieved_contexts}
    </section>

    <section>
      <h2>Corpus Summary</h2>
      <pre>{corpus_summary}</pre>
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
