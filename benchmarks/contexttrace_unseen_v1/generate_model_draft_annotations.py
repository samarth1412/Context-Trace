"""Generate a disclosed, local-model annotation draft for Pul to review."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.build_production_annotation_packets import (
    PacketError,
    _load_json,
    _packet_manifest,
    _write_json,
)
from benchmarks.contexttrace_unseen_v1.freeze_manifest import canonical_sha256


MODEL = "gemma3:4b"
MODEL_WEIGHTS_SHA256 = (
    "aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25"
)
SEED = 20260730
PROMPT_VERSION = "contexttrace-model-draft-v1"

VERDICTS = [
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
]
FAILURES = [
    "none",
    "retrieval_miss",
    "context_selection_error",
    "citation_mismatch",
    "answer_overreach",
    "contradiction",
    "insufficient_evidence",
    "should_have_abstained",
    "source_condition_failure",
]
ROOT_CAUSES = [
    "none",
    "retrieval_miss",
    "reranking_failure",
    "chunking_issue",
    "corpus_gap",
    "stale_or_superseded_source",
    "noncanonical_or_low_authority_source",
    "citation_mismatch",
    "answer_overreach",
    "insufficient_selected_context",
    "conflicting_contexts",
    "failure_to_abstain",
    "not_observable",
]
CITATION_STATES = [
    "not_applicable",
    "correct",
    "partial",
    "wrong_source",
    "missing",
    "malformed",
]
SOURCE_CONDITIONS = [
    "current_canonical",
    "current_noncanonical",
    "stale",
    "superseded",
    "low_authority",
    "conflicting_authorities",
    "unknown",
]
ABSTENTION = [
    "must_answer",
    "may_answer_with_qualification",
    "must_abstain",
]
def _response_schema() -> dict[str, Any]:
    evidence = {
        "type": "object",
        "additionalProperties": False,
        "required": ["chunk_id", "quote", "role"],
        "properties": {
            "chunk_id": {"type": "string"},
            "quote": {"type": "string", "minLength": 1},
            "role": {"enum": ["supporting", "contradicting"]},
        },
    }
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "claim_index",
            "claim_verdict",
            "failure_label",
            "primary_root_cause",
            "citation_state",
            "source_condition",
            "abstention_requirement",
            "evidence",
            "rationale",
        ],
        "properties": {
            "claim_index": {"type": "integer", "minimum": 1},
            "claim_verdict": {"enum": VERDICTS},
            "failure_label": {"enum": FAILURES},
            "primary_root_cause": {"enum": ROOT_CAUSES},
            "citation_state": {"enum": CITATION_STATES},
            "source_condition": {"enum": SOURCE_CONDITIONS},
            "abstention_requirement": {"enum": ABSTENTION},
            "evidence": {"type": "array", "items": evidence},
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {
            "claims": {"type": "array", "minItems": 1, "items": claim}
        },
    }


def _candidate_claims(answer: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    boundary = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"“\[])")
    for line_match in re.finditer(r"[^\n]+", answer):
        raw_line = line_match.group(0)
        left_trimmed = raw_line.lstrip()
        leading = len(raw_line) - len(left_trimmed)
        text = left_trimmed.rstrip()
        if not text:
            continue
        line_start = line_match.start() + leading
        cursor = 0
        for match in boundary.finditer(text):
            segment = text[cursor : match.start()].strip()
            if segment:
                start = line_start + cursor
                while answer[start].isspace():
                    start += 1
                end = start + len(segment)
                candidates.append({"text": answer[start:end], "start": start, "end": end})
            cursor = match.end()
        segment = text[cursor:].strip()
        if segment:
            start = line_start + cursor
            while answer[start].isspace():
                start += 1
            end = start + len(segment)
            candidates.append({"text": answer[start:end], "start": start, "end": end})
    for index, candidate in enumerate(candidates, start=1):
        candidate["claim_index"] = index
    return candidates


def _prompt(case: Mapping[str, Any], trace: Mapping[str, Any]) -> str:
    selected = set(trace["selected_context_ids"])
    chunks = [
        {
            "chunk_id": chunk["id"],
            "source_id": chunk["source_id"],
            "selected": chunk["id"] in selected,
            "text": chunk["text"],
        }
        for chunk in trace["retrieved_chunks"]
        if chunk["id"] in selected
    ]
    unselected_ids = [
        str(chunk["id"])
        for chunk in trace["retrieved_chunks"]
        if chunk["id"] not in selected
    ]
    materials = {
        "query": trace["query"],
        "answer": trace["answer"],
        "candidate_claims": [
            {"claim_index": item["claim_index"], "text": item["text"]}
            for item in _candidate_claims(str(trace["answer"]))
        ],
        "resolved_citations": trace["citations"],
        "selected_chunks": chunks,
        "unselected_retrieved_chunk_ids": unselected_ids,
        "sources": case["sources"],
        "source_condition_pair": case["source_condition_pair"],
    }
    return f"""You are drafting claim-level ContextTrace annotations for later
review. Use only the supplied materials. Do not assume that inline bracket text
is a resolved citation; only `resolved_citations` establishes resolution.

Rules:
- Label every factual assertion represented in `candidate_claims`. Return its
  integer `claim_index`; do not rewrite claim text. Omit only headings,
  greetings, and pure transitions. Pul may split a candidate more finely during
  review.
- Claims must be in candidate order and must not be duplicated.
- Ignore headings, greetings, and pure transitions rather than inventing claims.
- `supported` requires complete entailment by selected evidence.
- Use `partially_supported` when a material qualifier or component is missing.
- Use `contradicted` only for explicit incompatible evidence.
- Use `unverifiable` when the supplied trace cannot support a reliable verdict.
- A correct claim can still have a source-condition failure.
- Use source metadata and the temporal pair when deciding freshness/authority.
- Evidence `quote` must be an exact contiguous substring of the named chunk.
  Use the shortest quote that preserves the decisive proposition. Leave
  evidence empty if no supporting or contradicting text exists.
- Do not infer hidden retrieval stages. If the trace cannot distinguish causes,
  use `not_observable`.
- Apply the failure-label tie order: source condition, citation mismatch,
  should-have-abstained, earliest observable pipeline failure, then
  insufficient evidence.
- A resolved citation is `correct` only for the claim it supports. If citations
  are expected but none resolve, use `missing` or `malformed` as appropriate.
- Secondary arrays must not repeat the primary value.

Return only JSON matching the supplied schema.

Case materials:
{json.dumps(materials, ensure_ascii=False, sort_keys=True)}
"""


def _ollama(prompt: str, *, endpoint: str) -> dict[str, Any]:
    body = {
        "model": MODEL,
        "stream": False,
        "format": _response_schema(),
        "options": {
            "temperature": 0,
            "seed": SEED,
            "num_ctx": 65536,
        },
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise PacketError("Model response is not a JSON object.")
    parsed["_runtime"] = {
        key: result.get(key)
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        )
    }
    return parsed


def _evidence_span(
    evidence: Mapping[str, Any],
    *,
    trace: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> dict[str, Any] | None:
    chunks = {str(chunk["id"]): chunk for chunk in trace["retrieved_chunks"]}
    chunk_id = str(evidence["chunk_id"])
    if chunk_id not in chunks:
        raise PacketError(f"Unknown evidence chunk: {chunk_id}")
    chunk = chunks[chunk_id]
    quote = str(evidence["quote"])
    chunk_offset = str(chunk["text"]).find(quote)
    if chunk_offset < 0:
        selected = set(trace["selected_context_ids"])
        best: tuple[float, str, str] | None = None
        normalized_quote = " ".join(quote.lower().split())
        for candidate_id in selected:
            candidate_chunk = chunks[candidate_id]
            candidate_text = str(candidate_chunk["text"])
            pieces = [
                piece.strip()
                for piece in re.split(r"(?<=[.!?])\s+|\n+", candidate_text)
                if 20 <= len(piece.strip()) <= 1000
            ]
            for piece in pieces:
                score = difflib.SequenceMatcher(
                    None,
                    normalized_quote,
                    " ".join(piece.lower().split()),
                ).ratio()
                if best is None or score > best[0]:
                    best = (score, candidate_id, piece)
        if best is None or best[0] < 0.62:
            return None
        _, chunk_id, quote = best
        chunk = chunks[chunk_id]
        chunk_offset = str(chunk["text"]).find(quote)
        if chunk_offset < 0:
            raise PacketError("Aligned evidence quote is not exact.")
    source_id = str(chunk["source_id"])
    source_text = source_paths[source_id].read_text(encoding="utf-8")
    chunk_start = source_text.find(str(chunk["text"]))
    if chunk_start >= 0:
        start = chunk_start + chunk_offset
    else:
        matches: list[int] = []
        cursor = 0
        while True:
            position = source_text.find(quote, cursor)
            if position < 0:
                break
            matches.append(position)
            cursor = position + 1
        if len(matches) != 1:
            raise PacketError(
                f"Evidence quote cannot be uniquely mapped to {source_id}: {quote!r}"
            )
        start = matches[0]
    end = start + len(quote)
    if source_text[start:end] != quote:
        raise PacketError("Evidence source-offset validation failed.")
    return {
        "source_id": source_id,
        "source_snapshot_id": source_id,
        "chunk_id": chunk_id,
        "start": start,
        "end": end,
        "text": quote,
        "role": evidence["role"],
    }


def _case_fragment(
    case: Mapping[str, Any],
    trace: Mapping[str, Any],
    draft: Mapping[str, Any],
    *,
    packet: Path,
    completed_at: str,
) -> dict[str, Any]:
    source_by_id = {str(source["source_id"]): source for source in case["sources"]}
    source_paths = {
        source_id: packet / str(source["text_path"])
        for source_id, source in source_by_id.items()
    }
    raw_claims = draft.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise PacketError("Model draft contains no claims.")
    claims: list[Mapping[str, Any]] = []
    seen_claim_indices: set[int] = set()
    for claim in raw_claims:
        claim_index = int(claim["claim_index"])
        if claim_index in seen_claim_indices:
            continue
        seen_claim_indices.add(claim_index)
        claims.append(claim)
    candidates = {
        int(item["claim_index"]): item
        for item in _candidate_claims(str(trace["answer"]))
    }
    if any(int(claim["claim_index"]) not in candidates for claim in claims):
        raise PacketError("Model returned an unknown candidate claim index.")
    if [int(claim["claim_index"]) for claim in claims] != sorted(
        int(claim["claim_index"]) for claim in claims
    ):
        raise PacketError("Model claims are not in candidate order.")
    built: list[dict[str, Any]] = []
    for output_index, claim in enumerate(claims, start=1):
        candidate = candidates[int(claim["claim_index"])]
        answer_start = int(candidate["start"])
        answer_end = int(candidate["end"])
        proposed_spans = [
            _evidence_span(
                evidence,
                trace=trace,
                source_paths=source_paths,
            )
            for evidence in claim["evidence"]
        ]
        evidence_spans = [span for span in proposed_spans if span is not None]
        dropped_span_count = len(proposed_spans) - len(evidence_spans)
        basis_ids = sorted(
            {span["source_id"] for span in evidence_spans}
            or {
                str(source["source_id"])
                for source in case["sources"]
            }
        )
        basis_sources = [source_by_id[source_id] for source_id in basis_ids]
        effective_dates = sorted(
            {
                str(source["published_at"])
                for source in basis_sources
                if source.get("published_at")
            }
        )
        authority_rules = sorted(
            {
                str(source["authority_basis"])
                for source in basis_sources
                if source.get("authority_basis")
            }
        )
        confidence_value = 3
        built.append(
            {
                "claim_id": f"{case['case_id']}/claim-{output_index:03d}",
                "claim_text": candidate["text"],
                "answer_start": answer_start,
                "answer_end": answer_end,
                "propositional": True,
                "claim_verdict": claim["claim_verdict"],
                "failure_label": claim["failure_label"],
                "secondary_failure_labels": [],
                "primary_root_cause": claim["primary_root_cause"],
                "secondary_root_causes": [],
                "citation_state": claim["citation_state"],
                "source_condition": claim["source_condition"],
                "source_condition_basis": {
                    "snapshot_ids": basis_ids,
                    "effective_dates": effective_dates,
                    "authority_rule": "; ".join(authority_rules) or None,
                    "rationale": claim["rationale"],
                },
                "abstention_requirement": claim["abstention_requirement"],
                "evidence_spans": evidence_spans,
                "ambiguity_flags": [],
                "field_confidence": {
                    field: confidence_value
                    for field in (
                        "claim_boundary",
                        "claim_verdict",
                        "failure_label",
                        "primary_root_cause",
                        "citation_state",
                        "source_condition",
                        "abstention_requirement",
                        "evidence_spans",
                        "overall",
                    )
                },
                "rationale": claim["rationale"],
                "notes": (
                    "MODEL_DRAFT; requires field-by-field Pul review. "
                    f"Unaligned evidence suggestions omitted: {dropped_span_count}."
                ),
            }
        )
    return {
        "case_id": case["case_id"],
        "answer_sha256": hashlib.sha256(
            str(trace["answer"]).encode("utf-8")
        ).hexdigest(),
        "claims": built,
        "completed_at": completed_at,
        "case_notes": (
            "MODEL_DRAFT generated by pinned local Gemma; not a reviewed label."
        ),
    }


def generate(
    *,
    packet: Path,
    endpoint: str,
    limit: int | None,
    resume: bool,
) -> dict[str, Any]:
    assignment = _load_json(packet / "ASSIGNMENT.json")
    cases = list(assignment["cases"]["production"])
    if limit is not None:
        cases = cases[:limit]
    raw_root = packet / "model_raw"
    raw_root.mkdir(mode=0o700, exist_ok=True)
    prompt_hashes: dict[str, str] = {}
    completed: list[str] = []
    for position, case in enumerate(cases, start=1):
        case_id = str(case["case_id"])
        output_path = packet / "work" / "production" / f"{case_id}.json"
        raw_path = raw_root / f"{case_id}.json"
        if resume and raw_path.exists() and output_path.exists():
            existing = _load_json(output_path)
            if existing.get("completed_at"):
                completed.append(case_id)
                continue
        trace = _load_json(packet / str(case["trace_path"]))
        prompt = _prompt(case, trace)
        prompt_hashes[case_id] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        print(f"[{position}/{len(cases)}] {case_id}", flush=True)
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                raw = _ollama(prompt, endpoint=endpoint)
                timestamp = datetime.now(timezone.utc).isoformat()
                fragment = _case_fragment(
                    case,
                    trace,
                    raw,
                    packet=packet,
                    completed_at=timestamp,
                )
                _write_json(raw_path, raw)
                _write_json(output_path, fragment)
                completed.append(case_id)
                break
            except (
                KeyError,
                TypeError,
                ValueError,
                PacketError,
                json.JSONDecodeError,
                urllib.error.URLError,
            ) as exc:
                last_error = exc
                prompt += (
                    "\n\nYour previous response failed mechanical validation: "
                    f"{exc}. Return a corrected full JSON response."
                )
                print(f"  retry {attempt}: {exc}", flush=True)
        else:
            raise PacketError(f"{case_id} failed after retries: {last_error}")

    provenance: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_model_draft_provenance",
        "status": "model_draft_not_pul_reviewed",
        "model": MODEL,
        "model_weights_sha256": MODEL_WEIGHTS_SHA256,
        "runtime": "Ollama",
        "prompt_version": PROMPT_VERSION,
        "seed": SEED,
        "temperature": 0,
        "case_count_completed": len(completed),
        "case_ids_completed": completed,
        "prompt_sha256_by_case": prompt_hashes,
        "contexttrace_predictions_read": False,
        "phase6_case_results_read": False,
        "pul_review_complete": False,
    }
    provenance["payload_sha256"] = canonical_sha256(provenance)
    _write_json(packet / "MODEL_DRAFT_PROVENANCE.json", provenance, mode=0o400)
    _write_json(packet / "PACKET_MANIFEST.json", _packet_manifest(packet), mode=0o400)
    return provenance


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:11434/api/chat",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = generate(
            packet=args.packet,
            endpoint=args.endpoint,
            limit=args.limit,
            resume=args.resume,
        )
    except (OSError, PacketError, ValueError) as exc:
        raise SystemExit(f"Model-draft generation stopped: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
