from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    FormatChecker,
)


SCHEMA_PATH = Path(__file__).with_name("ANNOTATION_SCHEMA.json")
CATEGORICAL_FIELDS = (
    "claim_verdict",
    "failure_label",
    "primary_root_cause",
    "citation_state",
    "source_condition",
    "abstention_requirement",
)
MULTILABEL_FIELDS = (
    "secondary_failure_labels",
    "secondary_root_causes",
)
TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)


class AgreementError(ValueError):
    """Raised when raw annotation submissions cannot be compared safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgreementError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AgreementError(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise AgreementError(f"{path} must contain a JSON object.")
    return payload


def _schema() -> dict[str, Any]:
    return load_json(SCHEMA_PATH)


def _format_path(parts: Iterable[Any]) -> str:
    result = "$"
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def validate_annotation(document: Mapping[str, Any]) -> None:
    validator = Draft202012Validator(
        _schema(),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        first = errors[0]
        raise AgreementError(
            f"Annotation schema violation at {_format_path(first.absolute_path)}: "
            f"{first.message}"
        )
    if document["document_kind"] != "independent_annotation":
        raise AgreementError(
            "Agreement must be computed from raw independent annotations, "
            "not adjudicated or gold artifacts."
        )

    seen_cases: set[str] = set()
    for case in document["cases"]:
        case_id = str(case["case_id"])
        if case_id in seen_cases:
            raise AgreementError(f"Duplicate case_id in annotation: {case_id}")
        seen_cases.add(case_id)
        seen_claims: set[str] = set()
        boundaries: list[tuple[int, int, str]] = []
        for claim in case["claims"]:
            claim_id = str(claim["claim_id"])
            if claim_id in seen_claims:
                raise AgreementError(
                    f"Duplicate claim_id in case {case_id}: {claim_id}"
                )
            seen_claims.add(claim_id)
            start = int(claim["answer_start"])
            end = int(claim["answer_end"])
            if end <= start:
                raise AgreementError(
                    f"Claim {case_id}/{claim_id} has an empty or reversed boundary."
                )
            boundaries.append((start, end, claim_id))

            if not claim["propositional"]:
                diagnostic = (
                    set(CATEGORICAL_FIELDS)
                    | set(MULTILABEL_FIELDS)
                    | {
                        "source_condition_basis",
                        "evidence_spans",
                        "field_confidence",
                        "rationale",
                    }
                )
                exposed = sorted(diagnostic & set(claim))
                if exposed:
                    raise AgreementError(
                        f"Non-propositional claim {case_id}/{claim_id} has "
                        f"diagnostic fields: {exposed}"
                    )
                continue

            if claim["failure_label"] in claim["secondary_failure_labels"]:
                raise AgreementError(
                    f"Claim {case_id}/{claim_id} repeats its primary failure label."
                )
            if claim["primary_root_cause"] in claim["secondary_root_causes"]:
                raise AgreementError(
                    f"Claim {case_id}/{claim_id} repeats its primary root cause."
                )
            if (claim["failure_label"] == "none") != (
                claim["primary_root_cause"] == "none"
            ):
                raise AgreementError(
                    f"Claim {case_id}/{claim_id} has inconsistent none "
                    "failure/root-cause values."
                )
            seen_spans: set[tuple[Any, ...]] = set()
            for span in claim["evidence_spans"]:
                if span["end"] <= span["start"]:
                    raise AgreementError(
                        f"Claim {case_id}/{claim_id} has an empty evidence span."
                    )
                identity = (
                    span["source_id"],
                    span["source_snapshot_id"],
                    span["start"],
                    span["end"],
                    span["role"],
                )
                if identity in seen_spans:
                    raise AgreementError(
                        f"Claim {case_id}/{claim_id} has a duplicate evidence span."
                    )
                seen_spans.add(identity)

        ordered = sorted(boundaries)
        for (_, previous_end, previous_id), (
            current_start,
            _,
            current_id,
        ) in zip(ordered, ordered[1:]):
            if current_start < previous_end:
                raise AgreementError(
                    f"Claims {case_id}/{previous_id} and {case_id}/{current_id} overlap."
                )


def _case_index(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(case["case_id"]): case for case in document["cases"]}


def _propositional_claims(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [claim for claim in case["claims"] if claim["propositional"]]


def _boundary(claim: Mapping[str, Any]) -> tuple[int, int]:
    return int(claim["answer_start"]), int(claim["answer_end"])


def _safe_divide(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _harmonic(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _char_overlap(left: tuple[int, int], right: tuple[int, int]) -> int:
    return max(0, min(left[1], right[1]) - max(left[0], right[0]))


def _boundary_similarity(
    left: tuple[int, int],
    right: tuple[int, int],
) -> float:
    overlap = _char_overlap(left, right)
    if not overlap:
        return 0.0
    return 2 * overlap / ((left[1] - left[0]) + (right[1] - right[0]))


def _greedy_boundary_matches(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int, float]]:
    candidates: list[tuple[float, int, int]] = []
    for left_index, left_claim in enumerate(left):
        for right_index, right_claim in enumerate(right):
            score = _boundary_similarity(
                _boundary(left_claim),
                _boundary(right_claim),
            )
            if score:
                candidates.append((score, left_index, right_index))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_left: set[int] = set()
    used_right: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for score, left_index, right_index in candidates:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        matches.append((left_index, right_index, score))
    return matches


def boundary_agreement(
    left_cases: Mapping[str, Mapping[str, Any]],
    right_cases: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    shared_cases = sorted(set(left_cases) & set(right_cases))
    left_count = 0
    right_count = 0
    exact_matches = 0
    soft_match_sum = 0.0
    for case_id in shared_cases:
        left = _propositional_claims(left_cases[case_id])
        right = _propositional_claims(right_cases[case_id])
        left_count += len(left)
        right_count += len(right)
        left_boundaries = {_boundary(claim) for claim in left}
        right_boundaries = {_boundary(claim) for claim in right}
        exact_matches += len(left_boundaries & right_boundaries)
        soft_match_sum += sum(
            match[2] for match in _greedy_boundary_matches(left, right)
        )

    exact_precision = _safe_divide(exact_matches, right_count)
    exact_recall = _safe_divide(exact_matches, left_count)
    overlap_precision = _safe_divide(soft_match_sum, right_count)
    overlap_recall = _safe_divide(soft_match_sum, left_count)
    return {
        "shared_cases": len(shared_cases),
        "left_claims": left_count,
        "right_claims": right_count,
        "exact_matches": exact_matches,
        "exact_precision": exact_precision,
        "exact_recall": exact_recall,
        "exact_f1": _harmonic(exact_precision, exact_recall),
        "overlap_precision": overlap_precision,
        "overlap_recall": overlap_recall,
        "overlap_f1": _harmonic(overlap_precision, overlap_recall),
    }


def _exact_claim_pairs(
    left_cases: Mapping[str, Mapping[str, Any]],
    right_cases: Mapping[str, Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for case_id in sorted(set(left_cases) & set(right_cases)):
        left = {
            _boundary(claim): claim
            for claim in _propositional_claims(left_cases[case_id])
        }
        right = {
            _boundary(claim): claim
            for claim in _propositional_claims(right_cases[case_id])
        }
        pairs.extend((left[key], right[key]) for key in sorted(set(left) & set(right)))
    return pairs


def exact_agreement(left: Sequence[Any], right: Sequence[Any]) -> float | None:
    if not left:
        return None
    return sum(a == b for a, b in zip(left, right)) / len(left)


def cohen_kappa(left: Sequence[Any], right: Sequence[Any]) -> float | None:
    if not left or len(left) != len(right):
        return None
    observed = exact_agreement(left, right)
    assert observed is not None
    labels = set(left) | set(right)
    expected = sum(
        (left.count(label) / len(left)) * (right.count(label) / len(right))
        for label in labels
    )
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1 - expected)


def _prevalence(values: Sequence[Any]) -> dict[str, float]:
    if not values:
        return {}
    counts = Counter(str(value) for value in values)
    return {label: count / len(values) for label, count in sorted(counts.items())}


def krippendorff_alpha_nominal(units: Sequence[Sequence[Any]]) -> float | None:
    usable = [list(unit) for unit in units if len(unit) >= 2]
    if not usable:
        return None
    observed_disagreements = 0
    observed_pairs = 0
    values: list[Any] = []
    for unit in usable:
        values.extend(unit)
        for left, right in itertools.combinations(unit, 2):
            observed_pairs += 1
            observed_disagreements += left != right
    if not observed_pairs:
        return None
    observed = observed_disagreements / observed_pairs
    if len(values) < 2:
        return None
    counts = Counter(values)
    agreement_probability = sum(count * (count - 1) for count in counts.values()) / (
        len(values) * (len(values) - 1)
    )
    expected = 1 - agreement_probability
    if math.isclose(expected, 0.0):
        return None
    return 1 - observed / expected


def _tokens(text: str) -> Counter[str]:
    return Counter(token.casefold() for token in TOKEN_PATTERN.findall(text))


def evidence_token_f1(
    left_spans: Sequence[Mapping[str, Any]],
    right_spans: Sequence[Mapping[str, Any]],
) -> float | None:
    if not left_spans and not right_spans:
        return None
    left: Counter[tuple[str, str, str]] = Counter()
    right: Counter[tuple[str, str, str]] = Counter()
    for span, target in ((span, left) for span in left_spans):
        key = (str(span["source_id"]), str(span["role"]))
        for token, count in _tokens(str(span["text"])).items():
            target[(key[0], key[1], token)] += count
    for span, target in ((span, right) for span in right_spans):
        key = (str(span["source_id"]), str(span["role"]))
        for token, count in _tokens(str(span["text"])).items():
            target[(key[0], key[1], token)] += count
    overlap = sum((left & right).values())
    precision = _safe_divide(overlap, sum(right.values()))
    recall = _safe_divide(overlap, sum(left.values()))
    return _harmonic(precision, recall)


def evidence_character_iou(
    left_spans: Sequence[Mapping[str, Any]],
    right_spans: Sequence[Mapping[str, Any]],
) -> float | None:
    if not left_spans and not right_spans:
        return None

    def positions(
        spans: Sequence[Mapping[str, Any]],
    ) -> set[tuple[str, str, int]]:
        result: set[tuple[str, str, int]] = set()
        for span in spans:
            result.update(
                (
                    str(span["source_id"]),
                    str(span["role"]),
                    position,
                )
                for position in range(int(span["start"]), int(span["end"]))
            )
        return result

    left = positions(left_spans)
    right = positions(right_spans)
    union = left | right
    return len(left & right) / len(union) if union else None


def _mean(values: Iterable[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return sum(usable) / len(usable) if usable else None


def _multilabel_jaccard(left: Sequence[Any], right: Sequence[Any]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


def pairwise_agreement(
    left_document: Mapping[str, Any],
    right_document: Mapping[str, Any],
) -> dict[str, Any]:
    left_cases = _case_index(left_document)
    right_cases = _case_index(right_document)
    pairs = _exact_claim_pairs(left_cases, right_cases)
    categorical: dict[str, Any] = {}
    for field in CATEGORICAL_FIELDS:
        left = [pair[0][field] for pair in pairs]
        right = [pair[1][field] for pair in pairs]
        categorical[field] = {
            "eligible_claims": len(left),
            "exact_agreement": exact_agreement(left, right),
            "cohen_kappa": cohen_kappa(left, right),
            "prevalence_left": _prevalence(left),
            "prevalence_right": _prevalence(right),
        }

    multilabel: dict[str, Any] = {}
    for field in MULTILABEL_FIELDS:
        exact_values = [set(pair[0][field]) == set(pair[1][field]) for pair in pairs]
        multilabel[field] = {
            "eligible_claims": len(pairs),
            "exact_agreement": (
                sum(exact_values) / len(exact_values) if exact_values else None
            ),
            "mean_jaccard": _mean(
                _multilabel_jaccard(pair[0][field], pair[1][field]) for pair in pairs
            ),
        }

    span_token = [
        evidence_token_f1(pair[0]["evidence_spans"], pair[1]["evidence_spans"])
        for pair in pairs
    ]
    span_iou = [
        evidence_character_iou(
            pair[0]["evidence_spans"],
            pair[1]["evidence_spans"],
        )
        for pair in pairs
    ]
    return {
        "annotator_left": left_document["annotator_id"],
        "annotator_right": right_document["annotator_id"],
        "shared_case_count": len(set(left_cases) & set(right_cases)),
        "left_only_case_count": len(set(left_cases) - set(right_cases)),
        "right_only_case_count": len(set(right_cases) - set(left_cases)),
        "claim_boundaries": boundary_agreement(left_cases, right_cases),
        "exact_boundary_aligned_claims": len(pairs),
        "categorical_fields": categorical,
        "multilabel_fields": multilabel,
        "evidence_spans": {
            "eligible_claims": sum(value is not None for value in span_token),
            "mean_token_f1": _mean(span_token),
            "mean_character_iou": _mean(span_iou),
        },
    }


def _alpha_units(
    documents: Sequence[Mapping[str, Any]],
    field: str,
) -> list[list[Any]]:
    units: dict[tuple[str, int, int], list[Any]] = {}
    for document in documents:
        for case in document["cases"]:
            case_id = str(case["case_id"])
            for claim in _propositional_claims(case):
                key = (
                    case_id,
                    int(claim["answer_start"]),
                    int(claim["answer_end"]),
                )
                units.setdefault(key, []).append(claim[field])
    return list(units.values())


def analyze_agreement(
    documents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(documents) < 2:
        raise AgreementError("At least two independent annotation files are required.")
    for document in documents:
        validate_annotation(document)

    annotator_ids = [str(document["annotator_id"]) for document in documents]
    if len(set(annotator_ids)) != len(annotator_ids):
        raise AgreementError("Annotation files must have distinct annotator IDs.")
    manifests = {str(document["manifest_sha256"]) for document in documents}
    if len(manifests) != 1:
        raise AgreementError("Annotation files reference different dataset manifests.")
    guides = {str(document["guide_version"]) for document in documents}
    if len(guides) != 1:
        raise AgreementError("Annotation files use different guide versions.")
    policies = {str(document["claim_policy_version"]) for document in documents}
    if len(policies) != 1:
        raise AgreementError("Annotation files use different claim-policy versions.")

    pairwise = [
        pairwise_agreement(left, right)
        for left, right in itertools.combinations(documents, 2)
    ]
    alpha = {
        field: krippendorff_alpha_nominal(_alpha_units(documents, field))
        for field in CATEGORICAL_FIELDS
    }
    return {
        "schema_version": "1.0",
        "status": "pre_adjudication_human_agreement",
        "dataset_id": documents[0]["dataset_id"],
        "manifest_sha256": documents[0]["manifest_sha256"],
        "guide_version": documents[0]["guide_version"],
        "claim_policy_version": documents[0]["claim_policy_version"],
        "annotators": sorted(annotator_ids),
        "annotation_file_count": len(documents),
        "model_assistance": {
            str(document["annotator_id"]): document["model_assistance"]
            for document in documents
        },
        "pairwise": pairwise,
        "krippendorff_alpha_nominal": alpha,
        "policy": (
            "Every field is reported separately. No adjudicated value or combined "
            "agreement statistic is included."
        ),
    }


def _display(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# ContextTrace-Unseen-v1 pre-adjudication agreement",
        "",
        f"- Manifest: `{report['manifest_sha256']}`",
        f"- Guide: `{report['guide_version']}`",
        f"- Annotators: {', '.join(report['annotators'])}",
        "",
        "No adjudicated labels are included in these statistics.",
    ]
    for pair in report["pairwise"]:
        lines.extend(
            [
                "",
                f"## {pair['annotator_left']} vs {pair['annotator_right']}",
                "",
                "| Claim-boundary metric | Value |",
                "| --- | ---: |",
                f"| Exact F1 | {_display(pair['claim_boundaries']['exact_f1'])} |",
                f"| Overlap F1 | {_display(pair['claim_boundaries']['overlap_f1'])} |",
                "",
                "| Field | Eligible | Exact agreement | Cohen's kappa |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for field in CATEGORICAL_FIELDS:
            result = pair["categorical_fields"][field]
            lines.append(
                f"| {field} | {result['eligible_claims']} | "
                f"{_display(result['exact_agreement'])} | "
                f"{_display(result['cohen_kappa'])} |"
            )
        lines.extend(
            [
                "",
                "| Evidence-span metric | Value |",
                "| --- | ---: |",
                f"| Token F1 | {_display(pair['evidence_spans']['mean_token_f1'])} |",
                f"| Character IoU | "
                f"{_display(pair['evidence_spans']['mean_character_iou'])} |",
            ]
        )
    lines.extend(
        [
            "",
            "## Krippendorff's alpha by field",
            "",
            "| Field | Nominal alpha |",
            "| --- | ---: |",
        ]
    )
    for field in CATEGORICAL_FIELDS:
        lines.append(
            f"| {field} | {_display(report['krippendorff_alpha_nominal'][field])} |"
        )
    lines.extend(
        [
            "",
            "A combined kappa or alpha is intentionally not reported.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute field-specific pre-adjudication agreement for independent "
            "ContextTrace-Unseen-v1 annotations."
        )
    )
    parser.add_argument("--annotations", required=True, nargs="+", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-markdown", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    documents = [load_json(path) for path in args.annotations]
    report = analyze_agreement(documents)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"Agreement analyzed for {len(documents)} independent annotation files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
