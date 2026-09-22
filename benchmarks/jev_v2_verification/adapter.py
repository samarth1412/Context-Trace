"""Adapt frozen RAGTruth answer labels into shared-input verifier cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


LABEL_MAP = {
    "no_failure_detected": "supported",
    "partial_support": "partially_supported",
    "unsupported": "unsupported",
    "contradicted_answer": "contradicted",
}


class AdapterError(ValueError):
    """Raised when a source case cannot be adapted without inventing a label."""


def adapt_ragtruth_case_pack(
    source: str | Path,
    *,
    split: str,
    per_label: int | None = None,
    seed: int = 20260920,
    unit: str = "answer",
    exclude_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    source_path = Path(source)
    payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
    if str(payload.get("dataset") or "").casefold() != "ragtruth":
        raise AdapterError("The source case pack must declare dataset=RAGTruth.")
    if split not in {"development", "heldout"}:
        raise AdapterError("split must be development or heldout.")
    if unit not in {"answer", "sentence"}:
        raise AdapterError("unit must be answer or sentence.")
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise AdapterError("The source case pack has no cases.")

    adapted = []
    for row in rows:
        if unit == "answer":
            adapted.append(_adapt_answer_case(row, split=split))
        else:
            adapted.extend(_adapt_sentence_cases(row, split=split))
    excluded = set(exclude_case_ids or ())
    available_before_exclusion = len(adapted)
    adapted = [row for row in adapted if str(row["id"]) not in excluded]
    excluded_present = available_before_exclusion - len(adapted)
    if per_label is not None:
        if per_label < 1:
            raise AdapterError("per_label must be positive.")
        adapted = _stratified_sample(adapted, per_label=per_label, seed=seed)
    counts: dict[str, int] = defaultdict(int)
    for row in adapted:
        counts[str(row["expected_verdict"])] += 1
    return {
        "schema_version": "jev-v2-case-pack-1.0",
        "dataset": "RAGTruth",
        "split": split,
        "label_scope": (
            "answer_level"
            if unit == "answer"
            else "sentence_level_projected_from_upstream_answer_spans"
        ),
        "provenance": (
            "upstream_human_answer_side_hallucination_annotations"
            if unit == "answer"
            else "deterministic_sentence_projection_of_upstream_human_answer_spans"
        ),
        "independent_source_labels": unit == "answer",
        "source_case_pack": str(source_path),
        "source_case_pack_sha256": _sha256(source_path),
        "selection": {
            "method": "stable_hash_stratified_by_expected_verdict"
            if per_label is not None
            else "all_compatible_cases",
            "seed": seed if per_label is not None else None,
            "per_label_cap": per_label,
            "available_before_exclusion": available_before_exclusion,
            "excluded_case_id_count": len(excluded),
            "excluded_present_count": excluded_present,
            "excluded_case_ids_sha256": (
                hashlib.sha256("\n".join(sorted(excluded)).encode("utf-8")).hexdigest()
                if excluded
                else None
            ),
        },
        "limitations": [
            "RAGTruth labels answers and answer-side hallucination spans, not ContextTrace atomic claims.",
            (
                "The adapted task evaluates answer-level support."
                if unit == "answer"
                else "Sentence labels are deterministic projections from upstream answer spans, not independently annotated claim labels."
            ),
            "The adapter does not score source-span localization.",
            "RAGTruth does not provide an unverifiable class and has little unsupported coverage in this split.",
        ],
        "label_counts": dict(sorted(counts.items())),
        "cases": adapted,
    }


def _adapt_answer_case(row: object, *, split: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise AdapterError("Every source case must be an object.")
    labels = [str(value) for value in row.get("expected_labels") or []]
    if len(labels) != 1 or labels[0] not in LABEL_MAP:
        raise AdapterError(
            "Case %s has no lossless answer-label mapping: %r."
            % (row.get("id"), labels)
        )
    contexts = row.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise AdapterError("Case %s has no source context." % row.get("id"))
    clean_contexts = []
    for context in contexts:
        if not isinstance(context, dict):
            raise AdapterError("Case %s has an invalid context." % row.get("id"))
        context_id = str(context.get("id") or "").strip()
        text = str(context.get("text") or "")
        if not context_id or not text.strip():
            raise AdapterError("Case %s has an empty context." % row.get("id"))
        clean_contexts.append({"id": context_id, "text": text})
    metadata = row.get("ragtruth_metadata") or {}
    return {
        "id": str(row.get("id") or ""),
        "split": split,
        "dataset": "RAGTruth",
        "query": str(row.get("query") or ""),
        "claim": str(row.get("answer") or ""),
        "contexts": clean_contexts,
        "expected_verdict": LABEL_MAP[labels[0]],
        "label_scope": "answer_level",
        "upstream_label": labels[0],
        "upstream_response_id": str(metadata.get("response_id") or ""),
        "upstream_task_type": str(metadata.get("task_type") or ""),
        "upstream_model": str(metadata.get("model") or ""),
    }


def _adapt_sentence_cases(row: object, *, split: str) -> list[dict[str, Any]]:
    answer_case = _adapt_answer_case(row, split=split)
    assert isinstance(row, dict)
    answer = str(row.get("answer") or "")
    raw_spans = (row.get("ragtruth_metadata") or {}).get("answer_hallucination_spans") or []
    annotations = [
        annotation
        for annotation in raw_spans
        if isinstance(annotation, dict)
        and isinstance(annotation.get("start"), int)
        and isinstance(annotation.get("end"), int)
    ]
    projected = []
    for index, (start, end, sentence) in enumerate(_sentence_spans(answer), start=1):
        overlaps = [
            annotation
            for annotation in annotations
            if int(annotation["start"]) < end and int(annotation["end"]) > start
        ]
        if any("conflict" in str(item.get("label_type") or "").casefold() for item in overlaps):
            verdict = "contradicted"
        elif overlaps:
            verdict = "partially_supported"
        else:
            verdict = "supported"
        projected.append(
            {
                **answer_case,
                "id": "%s_s%03d" % (answer_case["id"], index),
                "claim": sentence,
                "expected_verdict": verdict,
                "label_scope": "sentence_level_projected_from_upstream_answer_spans",
                "answer_character_span": {"start": start, "end": end},
                "overlapping_upstream_annotations": [
                    {
                        "start": int(item["start"]),
                        "end": int(item["end"]),
                        "label_type": str(item.get("label_type") or ""),
                    }
                    for item in overlaps
                ],
            }
        )
    return projected


def _sentence_spans(value: str) -> list[tuple[int, int, str]]:
    spans = []
    for match in re.finditer(r"\S(?:.*?\S)?(?:[.!?]+(?=\s|$)|(?=\n)|$)", value, flags=re.DOTALL):
        start, end = match.span()
        text = match.group(0).strip()
        if text:
            leading = len(match.group(0)) - len(match.group(0).lstrip())
            trailing = len(match.group(0)) - len(match.group(0).rstrip())
            spans.append((start + leading, end - trailing, text))
    return spans


def _stratified_sample(
    rows: list[dict[str, Any]],
    *,
    per_label: int,
    seed: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["expected_verdict"])].append(row)
    selected = []
    for label, values in sorted(groups.items()):
        ordered = sorted(
            values,
            key=lambda row: hashlib.sha256(
                ("%s:%s:%s" % (seed, label, row["id"])).encode("utf-8")
            ).hexdigest(),
        )
        selected.extend(ordered[:per_label])
    return sorted(selected, key=lambda row: str(row["id"]))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-label", type=int)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--unit", choices=("answer", "sentence"), default="answer")
    parser.add_argument(
        "--exclude-case-pack",
        action="append",
        default=[],
        help="Case pack whose IDs must be excluded; may be repeated.",
    )
    args = parser.parse_args(argv)
    excluded_case_ids: set[str] = set()
    for case_pack in args.exclude_case_pack:
        excluded_payload = json.loads(Path(case_pack).read_text(encoding="utf-8"))
        excluded_rows = excluded_payload.get("cases")
        if not isinstance(excluded_rows, list):
            raise AdapterError("Excluded case pack %s has no cases list." % case_pack)
        excluded_case_ids.update(str(row.get("id") or "") for row in excluded_rows)
    excluded_case_ids.discard("")
    payload = adapt_ragtruth_case_pack(
        args.source,
        split=args.split,
        per_label=args.per_label,
        seed=args.seed,
        unit=args.unit,
        exclude_case_ids=excluded_case_ids,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(payload["cases"]), "label_counts": payload["label_counts"]}, indent=2))
    print("wrote %s" % output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
