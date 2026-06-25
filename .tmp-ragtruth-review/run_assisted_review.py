from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


SYSTEM_PROMPT = """You are reviewing RAGTruth answer-side hallucination labels against source contexts.
Return only valid JSON.

Rules:
- Select source_evidence_spans as short, exact, contiguous substrings copied from source_contexts.
- A valid span can support, contradict, or tightly bound the labeled answer span.
- Do not copy the model answer. Do not invent text. Do not use outside knowledge.
- If no fair source text supports, contradicts, or bounds the label, return an empty source_evidence_spans array and explain that briefly in review_notes.
- Prefer one or two minimal source spans. Use more only when multiple answer labels need separate evidence.
- Do not change taxonomy_override unless the expected label/root cause is clearly wrong.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--reviewer", default="Codex GPT-5.1 assisted source review")
    parser.add_argument("--retry", type=int, default=2)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")

    queue_path = Path(args.queue)
    output_path = Path(args.output)
    rows = load_jsonl(queue_path)
    existing = {str(row.get("case_id") or ""): row for row in load_jsonl(output_path) if row.get("case_id")}
    pending = [row for row in rows if str(row.get("case_id") or "") not in existing]
    if args.limit and args.limit > 0:
        pending = pending[: args.limit]

    reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    processed = 0
    with httpx.Client(timeout=120) as client:
        for row in pending:
            case_id = str(row.get("case_id") or "")
            payload = build_payload(row, model=args.model)
            result = None
            last_error = None
            for attempt in range(args.retry + 1):
                try:
                    response = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if response.status_code >= 400:
                        raise RuntimeError("%s: %s" % (response.status_code, response.text[:1000]))
                    raw = response.json()["choices"][0]["message"]["content"]
                    result = json.loads(raw)
                    break
                except Exception as exc:  # noqa: BLE001 - temp runner reports and retries API/JSON failures.
                    last_error = exc
                    time.sleep(2 + attempt)
            if result is None:
                raise RuntimeError("Failed case %s: %s" % (case_id, last_error))

            reviewed = reviewed_row(row, result, reviewer=args.reviewer, reviewed_at=reviewed_at)
            reviewed["source_evidence_spans"] = exact_context_spans(
                reviewed.get("source_evidence_spans") or [],
                row.get("source_contexts") or [],
            )
            existing[case_id] = reviewed
            write_jsonl_in_queue_order(rows, existing, output_path)
            processed += 1
            print(
                json.dumps(
                    {
                        "case_id": case_id,
                        "spans": len(reviewed["source_evidence_spans"]),
                        "processed_this_run": processed,
                        "completed_total": len(existing),
                        "queue_rows": len(rows),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    print("Processed %s rows; output=%s" % (processed, output_path))
    return 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def build_payload(row: dict[str, Any], *, model: str) -> dict[str, Any]:
    user_payload = {
        "case_id": row.get("case_id"),
        "source": row.get("source"),
        "expected_labels": row.get("expected_labels"),
        "expected_primary_root_cause": row.get("expected_primary_root_cause"),
        "expected_verdict_counts": row.get("expected_verdict_counts"),
        "query": row.get("query"),
        "answer": row.get("answer"),
        "answer_hallucination_spans": row.get("answer_hallucination_spans"),
        "source_contexts": row.get("source_contexts"),
        "output_schema": {
            "case_id": row.get("case_id"),
            "source_evidence_spans": ["exact source substring"],
            "review_notes": "brief rationale",
            "taxonomy_override": {
                "expected_labels": [],
                "expected_primary_root_cause": "",
                "expected_verdict_counts": {},
            },
        },
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
        ],
        "response_format": {"type": "json_object"},
    }


def reviewed_row(
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    reviewer: str,
    reviewed_at: str,
) -> dict[str, Any]:
    output = dict(row)
    output["review_status"] = "reviewed"
    output["reviewer"] = reviewer
    output["reviewed_at"] = reviewed_at
    notes = str(result.get("review_notes") or "").strip()
    prefix = "GPT-5.1 assisted review; not independent human sign-off."
    output["review_notes"] = "%s %s" % (prefix, notes) if notes else prefix
    spans = result.get("source_evidence_spans") or []
    output["source_evidence_spans"] = [str(span).strip() for span in spans if str(span).strip()]
    override = result.get("taxonomy_override")
    if isinstance(override, dict):
        output["taxonomy_override"] = {
            "expected_labels": list(override.get("expected_labels") or []),
            "expected_primary_root_cause": str(override.get("expected_primary_root_cause") or ""),
            "expected_verdict_counts": dict(override.get("expected_verdict_counts") or {}),
        }
    return output


def exact_context_spans(spans: list[str], contexts: list[dict[str, Any]]) -> list[str]:
    texts = [str(context.get("text") or "") for context in contexts if isinstance(context, dict)]
    accepted = []
    seen = set()
    for span in spans:
        exact = find_exact_or_whitespace_equivalent(span, texts)
        if exact and normalize(exact) not in seen:
            seen.add(normalize(exact))
            accepted.append(exact)
    return accepted


def find_exact_or_whitespace_equivalent(span: str, texts: list[str]) -> str:
    if not span.strip():
        return ""
    for text in texts:
        if span in text:
            return span
    normalized_span = normalize(span)
    for text in texts:
        normalized_text, index_map = normalize_with_map(text)
        start = normalized_text.find(normalized_span)
        if start >= 0:
            end = start + len(normalized_span)
            raw_start = index_map[start]
            raw_end = index_map[end - 1] + 1
            return text[raw_start:raw_end].strip()
    return ""


def normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def normalize_with_map(value: str) -> tuple[str, list[int]]:
    chars = []
    index_map = []
    in_space = True
    for index, char in enumerate(value):
        if char.isspace():
            if not in_space:
                chars.append(" ")
                index_map.append(index)
                in_space = True
            continue
        chars.append(char.casefold())
        index_map.append(index)
        in_space = False
    while chars and chars[-1] == " ":
        chars.pop()
        index_map.pop()
    return "".join(chars), index_map


def write_jsonl_in_queue_order(
    queue_rows: list[dict[str, Any]],
    reviewed_by_id: dict[str, dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        reviewed_by_id[str(row.get("case_id") or "")]
        for row in queue_rows
        if str(row.get("case_id") or "") in reviewed_by_id
    ]
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
