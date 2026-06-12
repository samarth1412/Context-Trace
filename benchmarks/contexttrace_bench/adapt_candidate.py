from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_LABEL_FIELDS = ("predicted", "predicted_labels", "failure_labels", "failure_label")
DEFAULT_VERDICT_FIELDS = ("predicted_verdicts", "verdicts", "claim_verdicts")
DEFAULT_VERDICT_COUNT_FIELDS = ("predicted_verdict_counts", "verdict_counts")
DEFAULT_ROOT_FIELDS = ("predicted_primary_root_cause", "primary_root_cause", "root_cause")
DEFAULT_CITATION_FIELDS = ("predicted_citation_statuses", "citation_statuses")
DEFAULT_SPAN_FIELDS = ("predicted_evidence_spans", "evidence_spans", "supporting_spans")
PRESETS = {
    "generic": {},
    "ragas": {
        "faithfulness_field": "faithfulness",
        "context_recall_field": "context_recall",
    },
    "deepeval": {
        "faithfulness_field": "faithfulness_score",
        "context_recall_field": "contextual_recall",
    },
    "phoenix": {
        "faithfulness_field": "faithfulness_score",
        "context_recall_field": "retrieval_relevance",
    },
    "trulens": {
        "faithfulness_field": "groundedness",
        "context_recall_field": "context_relevance",
    },
}


def adapt_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    system: str,
    version: str = "",
    preset: str = "generic",
    id_field: str = "id",
    labels_field: str | None = None,
    verdicts_field: str | None = None,
    verdict_counts_field: str | None = None,
    root_cause_field: str | None = None,
    citation_statuses_field: str | None = None,
    evidence_spans_field: str | None = None,
    latency_field: str | None = "latency_ms",
    cost_field: str | None = "cost_usd",
    faithfulness_field: str | None = None,
    context_recall_field: str | None = None,
    faithfulness_threshold: float = 0.75,
    context_recall_threshold: float = 0.50,
) -> dict[str, Any]:
    preset_values = PRESETS.get(preset)
    if preset_values is None:
        raise ValueError("Unknown adapter preset %s." % preset)
    faithfulness_field = faithfulness_field or preset_values.get("faithfulness_field")
    context_recall_field = context_recall_field or preset_values.get("context_recall_field")

    predictions = []
    for row in rows:
        case_id = _get(row, id_field)
        if case_id is None:
            continue
        labels = _labels_from_row(
            row,
            labels_field=labels_field,
            faithfulness_field=faithfulness_field,
            context_recall_field=context_recall_field,
            faithfulness_threshold=faithfulness_threshold,
            context_recall_threshold=context_recall_threshold,
        )
        verdict_counts = _dict_from_first(row, [verdict_counts_field, *DEFAULT_VERDICT_COUNT_FIELDS])
        verdicts = _list_from_first(row, [verdicts_field, *DEFAULT_VERDICT_FIELDS])
        if not verdict_counts:
            verdict_counts = _verdict_counts_from_labels(labels, verdicts)

        prediction: dict[str, Any] = {
            "id": str(case_id),
            "predicted": labels,
            "predicted_verdict_counts": verdict_counts,
        }
        root_cause = _first_value(row, [root_cause_field, *DEFAULT_ROOT_FIELDS])
        if root_cause is not None:
            prediction["predicted_primary_root_cause"] = str(root_cause)
        citation_statuses = _list_from_first(row, [citation_statuses_field, *DEFAULT_CITATION_FIELDS])
        if citation_statuses:
            prediction["predicted_citation_statuses"] = citation_statuses
        evidence_spans = _list_from_first(row, [evidence_spans_field, *DEFAULT_SPAN_FIELDS])
        if evidence_spans:
            prediction["predicted_evidence_spans"] = evidence_spans
        latency = _number_or_none(_get(row, latency_field) if latency_field else None)
        if latency is not None:
            prediction["latency_ms"] = latency
        cost = _number_or_none(_get(row, cost_field) if cost_field else None)
        if cost is not None:
            prediction["cost_usd"] = cost
        predictions.append(prediction)

    return {
        "system": system,
        "version": version,
        "adapter": "contexttrace_bench",
        "adapter_preset": preset,
        "predictions": predictions,
    }


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    suffix = input_path.suffix.lower()
    if suffix == ".jsonl":
        return [
            item
            for item in (
                json.loads(line)
                for line in input_path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            )
            if isinstance(item, dict)
        ]
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("predictions", "rows", "results", "cases"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("Could not find rows in %s." % input_path)


def write_candidate(candidate: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidate, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def _labels_from_row(
    row: dict[str, Any],
    *,
    labels_field: str | None,
    faithfulness_field: str | None,
    context_recall_field: str | None,
    faithfulness_threshold: float,
    context_recall_threshold: float,
) -> list[str]:
    labels = _list_from_first(row, [labels_field, *DEFAULT_LABEL_FIELDS])
    if labels:
        return labels

    faithfulness = _number_or_none(_get(row, faithfulness_field) if faithfulness_field else None)
    context_recall = _number_or_none(_get(row, context_recall_field) if context_recall_field else None)
    inferred: list[str] = []
    if faithfulness is not None and faithfulness < faithfulness_threshold:
        inferred.append("unsupported_answer")
    if context_recall is not None and context_recall < context_recall_threshold:
        inferred.append("should_have_abstained")
    return sorted(set(inferred)) or ["no_failure_detected"]


def _verdict_counts_from_labels(labels: list[str], verdicts: list[str]) -> dict[str, int]:
    counts = {
        "supported": 0,
        "partially_supported": 0,
        "unsupported": 0,
        "contradicted": 0,
        "unverifiable": 0,
    }
    for verdict in verdicts:
        if verdict in counts:
            counts[verdict] += 1
    if any(counts.values()):
        return counts
    labels_set = set(labels)
    if "contradicted_answer" in labels_set:
        counts["contradicted"] = 1
    elif "partial_support" in labels_set:
        counts["partially_supported"] = 1
    elif "unsupported_answer" in labels_set or "should_have_abstained" in labels_set:
        counts["unsupported"] = 1
    else:
        counts["supported"] = 1
    return counts


def _dict_from_first(row: dict[str, Any], fields: list[str | None]) -> dict[str, Any]:
    value = _first_value(row, fields)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip().startswith("{"):
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _list_from_first(row: dict[str, Any], fields: list[str | None]) -> list[str]:
    value = _first_value(row, fields)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [str(value)]


def _first_value(row: dict[str, Any], fields: list[str | None]) -> Any:
    for field in fields:
        if not field:
            continue
        value = _get(row, field)
        if value is not None and value != "":
            return value
    return None


def _get(row: dict[str, Any], field: str | None) -> Any:
    if not field:
        return None
    current: Any = row
    for part in str(field).split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapt evaluator output into ContextTrace-Bench candidate JSON.")
    parser.add_argument("--input", required=True, help="Input JSON, JSONL, or CSV evaluator output.")
    parser.add_argument("--output", required=True, help="Candidate JSON file to write.")
    parser.add_argument("--system", required=True, help="System name for the leaderboard row.")
    parser.add_argument("--version", default="", help="System or adapter version label.")
    parser.add_argument("--preset", default="generic", choices=sorted(PRESETS), help="Common field-name preset.")
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--labels-field", default=None)
    parser.add_argument("--verdicts-field", default=None)
    parser.add_argument("--verdict-counts-field", default=None)
    parser.add_argument("--root-cause-field", default=None)
    parser.add_argument("--citation-statuses-field", default=None)
    parser.add_argument("--evidence-spans-field", default=None)
    parser.add_argument("--latency-field", default="latency_ms")
    parser.add_argument("--cost-field", default="cost_usd")
    parser.add_argument("--faithfulness-field", default=None)
    parser.add_argument("--context-recall-field", default=None)
    parser.add_argument("--faithfulness-threshold", default=0.75, type=float)
    parser.add_argument("--context-recall-threshold", default=0.50, type=float)
    args = parser.parse_args(argv)

    candidate = adapt_candidate_rows(
        load_rows(args.input),
        system=args.system,
        version=args.version,
        preset=args.preset,
        id_field=args.id_field,
        labels_field=args.labels_field,
        verdicts_field=args.verdicts_field,
        verdict_counts_field=args.verdict_counts_field,
        root_cause_field=args.root_cause_field,
        citation_statuses_field=args.citation_statuses_field,
        evidence_spans_field=args.evidence_spans_field,
        latency_field=args.latency_field,
        cost_field=args.cost_field,
        faithfulness_field=args.faithfulness_field,
        context_recall_field=args.context_recall_field,
        faithfulness_threshold=args.faithfulness_threshold,
        context_recall_threshold=args.context_recall_threshold,
    )
    written = write_candidate(candidate, args.output)
    print("Wrote %s" % written)
    print("Predictions: %s" % len(candidate["predictions"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
