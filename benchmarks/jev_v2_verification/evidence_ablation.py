"""Measure evidence-selection loss without claiming unavailable oracle mappings.

RAGTruth supplies answer-side hallucination spans, but it does not supply
human-mapped source-side evidence spans.  This ablation therefore compares the
production-like selected-evidence condition with a complete-source-availability
condition.  The latter is an information-availability diagnostic, not an
oracle-evidence result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from contexttrace.verify.local_quality import LocalQualityJudge, select_local_evidence
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.spans import split_context_spans

from .run import (
    _write_json,
    load_case_pack,
    local_prediction,
    metrics,
    shared_input,
    stable_prediction,
)


def complete_source_input(case: dict[str, Any]) -> tuple[list[TraceContext], dict[str, Any]]:
    """Expose every deterministic source span, without selecting by the claim."""

    source_contexts = [
        TraceContext(id=str(item["id"]), text=str(item["text"]))
        for item in case["contexts"]
    ]
    spans = [
        span
        for context in source_contexts
        for span in split_context_spans(context)
    ]
    contexts = [
        TraceContext(
            id="%s:%s:%s" % (span.context_id, span.start_char, span.end_char),
            text=span.text,
        )
        for span in spans
    ]
    state = {
        "query": str(case["query"]),
        "claim": str(case["claim"]),
        "available_evidence": [
            {"id": context.id, "text": context.text}
            for context in contexts
        ],
    }
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return contexts, {
        "input_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "evaluation_label_sent": False,
        "sent_fields": ["query", "claim", "available_evidence"],
        "exact_input": state,
        "source_context_count": len(source_contexts),
        "available_span_count": len(contexts),
        "condition": "complete_source_availability",
        "is_oracle_evidence": False,
    }


def run_evidence_ablation(
    cases: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    nli: object | None = None,
    nli_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deterministic = LocalQualityJudge()
    with_nli = LocalQualityJudge(nli=nli) if nli is not None else None
    rows = []
    for case in cases:
        selected_contexts, selected_audit = shared_input(case)
        source_contexts, source_audit = complete_source_input(case)
        selected_internal = _internal_selection(case, selected_contexts)
        source_internal = _internal_selection(case, source_contexts)
        conditions = {
            "selected_evidence": _predictions(
                case,
                selected_contexts,
                deterministic=deterministic,
                with_nli=with_nli,
            ),
            "complete_source_availability": _predictions(
                case,
                source_contexts,
                deterministic=deterministic,
                with_nli=with_nli,
            ),
        }
        rows.append(
            {
                "case_id": case["id"],
                "expected_verdict": case["expected_verdict"],
                "input_audits": {
                    "selected_evidence": selected_audit,
                    "complete_source_availability": source_audit,
                },
                "local_quality_internal_selection": {
                    "selected_evidence": selected_internal,
                    "complete_source_availability": source_internal,
                    "identical_text_sequence": [item["text_sha256"] for item in selected_internal]
                    == [item["text_sha256"] for item in source_internal],
                },
                "conditions": conditions,
            }
        )

    systems = list(rows[0]["conditions"]["selected_evidence"]) if rows else []
    return {
        "experiment": "contexttrace_evidence_availability_ablation",
        "schema_version": "1.0",
        "split": split_metadata,
        "cases_completed": len(rows),
        "conditions": {
            "selected_evidence": "The shared local selector's top spans, matching the Jev-v2 comparison.",
            "complete_source_availability": (
                "Every deterministic span from the RAGTruth source is available to the verifier. "
                "This is not human-mapped oracle evidence."
            ),
        },
        "interpretation": {
            "selected_wrong_complete_correct": "candidate evidence-selection loss",
            "selected_correct_complete_wrong": "candidate evidence dilution or verifier instability",
            "both_wrong": "candidate verifier limitation or projected-label noise",
            "causal_claim_allowed": False,
            "reason": (
                "RAGTruth has no human source-side evidence mapping, and the verifiers retain "
                "their own internal scoring or selection procedures."
            ),
        },
        "stable_defaults_changed": False,
        "remote_inference": False,
        "jev_run": False,
        "jev_not_run_reason": (
            "The complete source is not selected minimal evidence, and the existing held-out Jev run "
            "must not be reused for prompt or threshold tuning."
        ),
        "nli": nli_metadata,
        "internal_selector_equivalence": {
            "identical_cases": sum(
                bool(row["local_quality_internal_selection"]["identical_text_sequence"])
                for row in rows
            ),
            "total_cases": len(rows),
            "meaning": (
                "LocalQualityJudge applies its selector internally. Identical cases received the "
                "same ordered span texts in both availability conditions."
            ),
        },
        "metrics": {
            system: paired_metrics(rows, system)
            for system in systems
        },
        "rows": rows,
    }


def _internal_selection(
    case: dict[str, Any],
    contexts: list[TraceContext],
) -> list[dict[str, Any]]:
    spans = select_local_evidence(
        query=str(case["query"]),
        claim=str(case["claim"]),
        contexts=contexts,
        limit=8,
    )
    return [
        {
            "context_id": span.context_id,
            "text_sha256": hashlib.sha256(span.text.encode("utf-8")).hexdigest(),
            "characters": len(span.text),
        }
        for span in spans
    ]


def _predictions(
    case: dict[str, Any],
    contexts: list[TraceContext],
    *,
    deterministic: LocalQualityJudge,
    with_nli: LocalQualityJudge | None,
) -> dict[str, Any]:
    output = {
        "stable_semantic": stable_prediction(case, contexts),
        "local_deterministic": local_prediction(case, contexts, deterministic),
    }
    if with_nli is not None:
        output["local_deterministic_plus_nli"] = local_prediction(case, contexts, with_nli)
    return output


def paired_metrics(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    condition_metrics = {}
    for condition in ("selected_evidence", "complete_source_availability"):
        metric_rows = [
            {
                "case_id": row["case_id"],
                "expected_verdict": row["expected_verdict"],
                "predictions": {system: row["conditions"][condition][system]},
            }
            for row in rows
        ]
        condition_metrics[condition] = metrics(metric_rows, system)

    transitions = {
        "both_correct": [],
        "selected_wrong_complete_correct": [],
        "selected_correct_complete_wrong": [],
        "both_wrong": [],
    }
    verdict_changes = []
    for row in rows:
        gold = row["expected_verdict"]
        selected = row["conditions"]["selected_evidence"][system]["verdict"]
        complete = row["conditions"]["complete_source_availability"][system]["verdict"]
        selected_correct = selected == gold
        complete_correct = complete == gold
        if selected_correct and complete_correct:
            bucket = "both_correct"
        elif not selected_correct and complete_correct:
            bucket = "selected_wrong_complete_correct"
        elif selected_correct and not complete_correct:
            bucket = "selected_correct_complete_wrong"
        else:
            bucket = "both_wrong"
        transitions[bucket].append(str(row["case_id"]))
        if selected != complete:
            verdict_changes.append(
                {
                    "case_id": row["case_id"],
                    "expected_verdict": gold,
                    "selected_evidence_verdict": selected,
                    "complete_source_verdict": complete,
                }
            )
    return {
        **condition_metrics,
        "paired_transitions": {
            key: {"count": len(case_ids), "case_ids": case_ids}
            for key, case_ids in transitions.items()
        },
        "verdict_changes": verdict_changes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-path")
    args = parser.parse_args(argv)

    split_metadata, cases = load_case_pack(args.cases, expected_split=args.split)
    nli = nli_metadata = None
    if args.model_path:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        artifact = verify_nli_artifact(args.model_path)
        nli = build_pinned_nli(args.model_path)
        nli_metadata = {
            **artifact,
            "model_path": str(Path(args.model_path).resolve()),
            "automatic_download": False,
            "remote_inference": False,
        }
    result = run_evidence_ablation(
        cases,
        split_metadata=split_metadata,
        nli=nli,
        nli_metadata=nli_metadata,
    )
    _write_json(Path(args.output), result)
    print(json.dumps({"output": args.output, "metrics": result["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
