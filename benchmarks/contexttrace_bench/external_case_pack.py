from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


DEFAULT_LABEL_MAP = {
    "answer_overreach": "partial_support",
    "baseless": "partial_support",
    "conflict": "contradicted_answer",
    "conflicted": "contradicted_answer",
    "contradicted": "contradicted_answer",
    "contradicted_answer": "contradicted_answer",
    "contradiction": "contradicted_answer",
    "correct": "no_failure_detected",
    "faithful": "no_failure_detected",
    "grounded": "no_failure_detected",
    "hallucinated": "partial_support",
    "hallucination": "partial_support",
    "no_failure": "no_failure_detected",
    "no_failure_detected": "no_failure_detected",
    "not_supported": "partial_support",
    "partial": "partial_support",
    "partial_support": "partial_support",
    "should_abstain": "should_have_abstained",
    "should_have_abstained": "should_have_abstained",
    "supported": "no_failure_detected",
    "unsupported": "unsupported",
    "unsupported_answer": "unsupported_answer",
    "unverifiable": "unsupported",
}

DEFAULT_ROOT_CAUSE_BY_LABEL = {
    "contradicted_answer": "conflicting_contexts",
    "no_failure_detected": "no_failure_detected",
    "partial_support": "answer_overreach",
    "should_have_abstained": "retrieval_gap",
    "unsupported": "answer_overreach",
    "unsupported_answer": "answer_overreach",
}


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        rows = [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    else:
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = _first_list(payload, ("cases", "rows", "data", "examples", "items"))
        else:
            rows = []
    return [row for row in rows if isinstance(row, dict)]


def write_case_pack(case_pack: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(case_pack, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def adapt_external_rows(
    rows: list[dict[str, Any]],
    *,
    dataset: str,
    source_name: str | None = None,
    id_field: str = "id",
    query_field: str = "query",
    answer_field: str = "answer",
    contexts_field: str = "contexts",
    label_field: str = "expected_label",
    root_cause_field: str = "expected_primary_root_cause",
    evidence_spans_field: str = "expected_evidence_spans",
    limit: int | None = None,
    sample_size: int | None = None,
    sample_seed: int = 13,
    stratify_by: list[str] | None = None,
) -> dict[str, Any]:
    if limit is not None and sample_size is not None:
        raise ValueError("Use either limit or sample_size, not both.")
    if not str(dataset or "").strip():
        raise ValueError("dataset is required.")

    prepared: list[dict[str, Any]] = []
    skipped_missing_answer = 0
    skipped_missing_context = 0
    for index, row in enumerate(rows):
        case = _case_from_row(
            row,
            index=index,
            dataset=dataset,
            source_name=source_name,
            id_field=id_field,
            query_field=query_field,
            answer_field=answer_field,
            contexts_field=contexts_field,
            label_field=label_field,
            root_cause_field=root_cause_field,
            evidence_spans_field=evidence_spans_field,
        )
        if not case["answer"]:
            skipped_missing_answer += 1
            continue
        if not case["contexts"]:
            skipped_missing_context += 1
            continue
        prepared.append({"index": index, "row": row, "case": case})

    selected, sampling = _select_rows(
        prepared,
        limit=limit,
        sample_size=sample_size,
        sample_seed=sample_seed,
        stratify_by=stratify_by or [],
    )
    cases = [item["case"] for item in selected]
    duplicate_case_ids = _duplicates([str(case.get("id") or "") for case in cases])
    if duplicate_case_ids:
        raise ValueError(
            "External case IDs must be unique after normalization; duplicates: %s"
            % ", ".join(duplicate_case_ids[:10])
        )
    return {
        "description": (
            "%s case pack adapted for ContextTrace external validation from generic JSON/JSONL rows."
            % dataset
        ),
        "dataset": dataset,
        "adapter": "generic_external_contexttrace_case_pack",
        "source_files": {"rows": "external rows supplied by --input"},
        "cases": cases,
        "stats": {
            "input_rows": len(rows),
            "eligible_cases": len(prepared),
            "output_cases": len(cases),
            "skipped_missing_answer": skipped_missing_answer,
            "skipped_missing_context": skipped_missing_context,
            "sampling": sampling,
        },
        "limitations": [
            (
                "Generic external case packs preserve upstream labels as supplied; "
                "publishable claims require documenting the upstream dataset and labeling protocol."
            ),
            (
                "Evidence-span metrics are only meaningful when expected_evidence_spans "
                "are supplied by the external dataset or an independent reviewer."
            ),
        ],
        "notes": [
            (
                "Use this adapter for CRAG/ARES-style exports after normalizing rows "
                "to query, answer, contexts, and expected_label fields."
            ),
            "Rows without answer text or contexts are skipped because ContextTrace cannot verify them fairly.",
        ],
    }


def _case_from_row(
    row: dict[str, Any],
    *,
    index: int,
    dataset: str,
    source_name: str | None,
    id_field: str,
    query_field: str,
    answer_field: str,
    contexts_field: str,
    label_field: str,
    root_cause_field: str,
    evidence_spans_field: str,
) -> dict[str, Any]:
    case_id = str(_field_value(row, id_field, default=index) or index)
    expected_labels = _expected_labels(_field_value(row, label_field, default=None))
    root_cause = str(_field_value(row, root_cause_field, default="") or "").strip()
    if not root_cause:
        root_cause = _root_cause_for_labels(expected_labels)
    evidence_spans = _string_list(_field_value(row, evidence_spans_field, default=[]))
    return {
        "id": _safe_case_id(dataset, case_id),
        "source": str(source_name or row.get("source") or dataset),
        "note": "Adapted from generic external row %s." % case_id,
        "query": str(_field_value(row, query_field, default=row.get("question") or row.get("prompt") or "") or ""),
        "answer": str(_field_value(row, answer_field, default=row.get("response") or row.get("output") or "") or ""),
        "contexts": _contexts_from_row(row, contexts_field=contexts_field, dataset=dataset, case_id=case_id),
        "citations": _citations_from_row(row),
        "expected_labels": expected_labels,
        "expected_verdict_scope": str(row.get("expected_verdict_scope") or "answer_label"),
        "expected_verdict_counts": dict(row.get("expected_verdict_counts") or {}),
        "expected_citation_statuses": _string_list(row.get("expected_citation_statuses") or []),
        "expected_should_abstain": row.get("expected_should_abstain"),
        "expected_primary_root_cause": root_cause,
        "expected_evidence_spans": evidence_spans,
        "dataset_metadata": {
            "dataset": dataset,
            "source_row_id": case_id,
            "upstream_metadata": dict(row.get("metadata") or {}),
        },
    }


def _select_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int | None,
    sample_size: int | None,
    sample_seed: int,
    stratify_by: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sample_size is not None:
        sample_size = max(0, int(sample_size))
        selected = _stratified_sample(rows, sample_size=sample_size, sample_seed=sample_seed, stratify_by=stratify_by)
        return selected, {
            "method": "stratified" if stratify_by else "random",
            "sample_size": sample_size,
            "sample_seed": int(sample_seed),
            "stratify_by": list(stratify_by),
            "eligible_cases": len(rows),
        }
    if limit is not None:
        return rows[: int(limit)], {"method": "first_n", "limit": int(limit), "eligible_cases": len(rows)}
    return rows, {"method": "none", "eligible_cases": len(rows)}


def _stratified_sample(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    sample_seed: int,
    stratify_by: list[str],
) -> list[dict[str, Any]]:
    if sample_size >= len(rows):
        return list(rows)
    if not stratify_by:
        rng = random.Random(sample_seed)
        return sorted(rng.sample(rows, sample_size), key=lambda item: item["index"])
    by_key: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for item in rows:
        by_key.setdefault(_stratum_key(item["row"], item["case"], stratify_by), []).append(item)
    rng = random.Random(sample_seed)
    selected: list[dict[str, Any]] = []
    keys = sorted(by_key)
    while len(selected) < sample_size and keys:
        progressed = False
        for key in list(keys):
            bucket = by_key[key]
            if not bucket:
                keys.remove(key)
                continue
            selected.append(bucket.pop(rng.randrange(len(bucket))))
            progressed = True
            if len(selected) >= sample_size:
                break
        if not progressed:
            break
    return sorted(selected, key=lambda item: item["index"])


def _stratum_key(row: dict[str, Any], case: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    values = []
    for field in fields:
        if field == "expected_label":
            values.append("|".join(case.get("expected_labels") or []))
        else:
            values.append(str(_field_value(row, field, default=case.get(field) or "") or ""))
    return tuple(values)


def _contexts_from_row(
    row: dict[str, Any],
    *,
    contexts_field: str,
    dataset: str,
    case_id: str,
) -> list[dict[str, Any]]:
    raw_contexts = _field_value(row, contexts_field, default=None)
    if raw_contexts is None:
        raw_contexts = (
            row.get("retrieved_context")
            or row.get("documents")
            or row.get("passages")
            or row.get("context")
        )
    if isinstance(raw_contexts, str):
        raw_items: list[Any] = [raw_contexts]
    elif isinstance(raw_contexts, list):
        raw_items = raw_contexts
    else:
        raw_items = []
    contexts = []
    for index, item in enumerate(raw_items):
        context = _context_from_item(item, index=index, dataset=dataset, case_id=case_id)
        if context:
            contexts.append(context)
    return contexts


def _context_from_item(item: Any, *, index: int, dataset: str, case_id: str) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        metadata: dict[str, Any] = {}
        context_id = "%s_%s_context_%s" % (_slug(dataset), _slug(case_id), index)
    elif isinstance(item, dict):
        text = str(
            item.get("text")
            or item.get("content")
            or item.get("passage")
            or item.get("document")
            or ""
        ).strip()
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"id", "doc_id", "source_id", "text", "content", "passage", "document"}
        }
        context_id = str(item.get("id") or item.get("doc_id") or item.get("source_id") or "")
        context_id = context_id or "%s_%s_context_%s" % (_slug(dataset), _slug(case_id), index)
    else:
        return None
    if not text:
        return None
    return {"id": context_id, "text": text, "metadata": metadata}


def _citations_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    citations = row.get("citations") or []
    if not isinstance(citations, list):
        return []
    output = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id") or item.get("doc_id") or item.get("chunk_id")
        claim = item.get("claim") or item.get("text") or ""
        if source_id:
            output.append({"claim": str(claim), "source_id": str(source_id)})
    return output


def _expected_labels(value: Any) -> list[str]:
    labels = _string_list(value)
    if not labels:
        return ["no_failure_detected"]
    normalized = []
    for label in labels:
        mapped = DEFAULT_LABEL_MAP.get(label.lower().strip(), label)
        normalized.append(mapped)
    return _dedupe(normalized)


def _root_cause_for_labels(labels: list[str]) -> str:
    for label in labels:
        root_cause = DEFAULT_ROOT_CAUSE_BY_LABEL.get(label)
        if root_cause:
            return root_cause
    return "answer_overreach"


def _field_value(row: dict[str, Any], field: str, *, default: Any) -> Any:
    if not field:
        return default
    current: Any = row
    for part in str(field).split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _first_list(payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        output = []
        for item in value:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, dict):
                output.append(str(item.get("label") or item.get("text") or item.get("value") or ""))
            else:
                output.append(str(item))
        return [item for item in output if item]
    return [str(value)]


def _safe_case_id(dataset: str, case_id: str) -> str:
    prefix = _slug(dataset)
    value = _slug(case_id)
    if value.startswith(prefix + "_"):
        return value
    return "%s_%s" % (prefix, value)


def _slug(value: object) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "case"))
    text = "_".join(part for part in text.split("_") if part)
    return text or "case"


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adapt generic external JSON/JSONL rows into a ContextTrace case pack."
    )
    parser.add_argument("--input", required=True, help="Input JSON or JSONL rows.")
    parser.add_argument("--output", required=True, help="ContextTrace case-pack JSON to write.")
    parser.add_argument("--dataset", required=True, help="External dataset name, for example CRAG or ARES.")
    parser.add_argument("--source-name", default=None, help="Optional source label for all cases.")
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--query-field", default="query")
    parser.add_argument("--answer-field", default="answer")
    parser.add_argument("--contexts-field", default="contexts")
    parser.add_argument("--label-field", default="expected_label")
    parser.add_argument("--root-cause-field", default="expected_primary_root_cause")
    parser.add_argument("--evidence-spans-field", default="expected_evidence_spans")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=13)
    parser.add_argument(
        "--stratify-by",
        default="",
        help="Comma-separated row fields for deterministic stratified sampling.",
    )
    args = parser.parse_args(argv)

    rows = load_rows(args.input)
    case_pack = adapt_external_rows(
        rows,
        dataset=args.dataset,
        source_name=args.source_name,
        id_field=args.id_field,
        query_field=args.query_field,
        answer_field=args.answer_field,
        contexts_field=args.contexts_field,
        label_field=args.label_field,
        root_cause_field=args.root_cause_field,
        evidence_spans_field=args.evidence_spans_field,
        limit=args.limit,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        stratify_by=[item.strip() for item in args.stratify_by.split(",") if item.strip()],
    )
    written = write_case_pack(case_pack, args.output)
    print("Wrote: %s" % written)
    print("Dataset: %s" % case_pack["dataset"])
    print("Cases: %s" % len(case_pack["cases"]))
    print("Eligible cases: %s" % case_pack["stats"]["eligible_cases"])
    print("Sampling: %s" % json.dumps(case_pack["stats"]["sampling"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
