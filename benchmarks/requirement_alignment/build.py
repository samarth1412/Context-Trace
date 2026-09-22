"""Build an audited requirement-alignment dataset from the WiCE train split."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from contexttrace.verify.atomic_coverage import decompose_atomic_requirements


TRAIN_SHA256 = "3ef74c7203e1d9b369cb2c145e764d8ab4743f008f9765fa47f9bdd6ffa2d2e1"
TRAIN_URL = (
    "https://raw.githubusercontent.com/ryokamoi/wice/"
    "ddeb6c183665e2a20c5f03c5aa07f03888b9870f/"
    "data/entailment_retrieval/claim/train.jsonl"
)
SEED = 20260926
INTERNAL_VALIDATION_FRACTION = 0.15
SOURCE_LABELS = {"supported", "partially_supported"}
CONTENT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


class AlignmentDataError(RuntimeError):
    """Raised when training-data construction violates its provenance contract."""


def requirement_spans(claim: str) -> list[dict[str, Any]]:
    """Return exact spans in a whitespace-normalized claim."""

    normalized = " ".join(str(claim or "").split()).strip()
    if not normalized:
        return []
    output = []
    cursor = 0
    for requirement in decompose_atomic_requirements(normalized):
        candidate = requirement
        start = normalized.find(candidate, cursor)
        if start < 0 and candidate[-1:] in ".!?":
            candidate = candidate[:-1]
            start = normalized.find(candidate, cursor)
        if start < 0:
            start = normalized.find(candidate)
        if start < 0:
            raise AlignmentDataError("Atomic requirement is not an exact claim substring.")
        end = start + len(candidate)
        output.append(
            {
                "id": "r%02d" % len(output),
                "text": normalized[start:end],
                "start_char": start,
                "end_char": end,
            }
        )
        cursor = end
    return output


def build_dataset(
    rows: list[dict[str, Any]],
    *,
    excluded_claims: set[str] | None = None,
    validation_fraction: float = INTERNAL_VALIDATION_FRACTION,
    seed: int = SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not 0.0 < validation_fraction < 0.5:
        raise AlignmentDataError("validation_fraction must be between zero and 0.5.")
    excluded = excluded_claims or set()
    eligible, exclusions = _eligible_cases(rows, excluded_claims=excluded)
    split_by_case = _case_splits(
        eligible,
        validation_fraction=validation_fraction,
        seed=seed,
    )
    examples = []
    case_records = []
    for row in eligible:
        case_id = _case_id(row)
        split = split_by_case[case_id]
        built, record = _case_examples(row, split=split)
        examples.extend(built)
        case_records.append(record)
    if not examples:
        raise AlignmentDataError("No alignment examples were constructed.")
    dataset = {
        "schema_version": "contexttrace-requirement-alignment-1.0",
        "dataset": "WiCE-derived requirement alignment",
        "source": {
            "dataset": "WiCE",
            "split": "train",
            "url": TRAIN_URL,
            "sha256": TRAIN_SHA256,
        },
        "construction": {
            "seed": seed,
            "internal_validation_fraction": validation_fraction,
            "case_level_split": True,
            "normalized_claim_deduplication": True,
            "evaluation_claims_excluded": True,
            "labels_used_for_training_targets_only": True,
            "requirement_text_is_exact_normalized_claim_substring": True,
            "negative_types": [
                "gold_partial_group",
                "synthetic_drop_one",
                "same_document_hard_negative",
            ],
        },
        "examples": examples,
    }
    audit = audit_dataset(
        dataset,
        case_records=case_records,
        excluded_claims=excluded,
        exclusions=exclusions,
    )
    return dataset, audit


def audit_dataset(
    dataset: dict[str, Any],
    *,
    case_records: list[dict[str, Any]],
    excluded_claims: set[str],
    exclusions: dict[str, int],
) -> dict[str, Any]:
    examples = list(dataset.get("examples") or [])
    ids = [str(row["id"]) for row in examples]
    if len(ids) != len(set(ids)):
        raise AlignmentDataError("Example ids are not unique.")
    case_splits: dict[str, set[str]] = defaultdict(set)
    claim_splits: dict[str, set[str]] = defaultdict(set)
    exact_requirements = True
    drop_one_valid = True
    inputs_contain_targets = False
    for row in examples:
        case_splits[str(row["source"]["case_id"])].add(str(row["split"]))
        claim_hash = _text_hash(str(row["input"]["claim"]))
        claim_splits[claim_hash].add(str(row["split"]))
        requirement = row["input"].get("requirement")
        if requirement:
            start = int(requirement["start_char"])
            end = int(requirement["end_char"])
            exact_requirements = exact_requirements and (
                row["input"]["claim"][start:end] == requirement["text"]
            )
        construction = row["source"]["construction"]
        if construction == "synthetic_drop_one":
            removed = set(row["source"].get("removed_context_ids") or [])
            present = {item["id"] for item in row["input"]["evidence"]}
            drop_one_valid = drop_one_valid and bool(removed) and removed.isdisjoint(present)
        inputs_contain_targets = inputs_contain_targets or any(
            key in row["input"] for key in ("label", "target", "source_label")
        )
    overlap = sorted(set(claim_splits) & excluded_claims)
    valid = bool(
        examples
        and all(len(value) == 1 for value in case_splits.values())
        and all(len(value) == 1 for value in claim_splits.values())
        and not overlap
        and exact_requirements
        and drop_one_valid
        and not inputs_contain_targets
    )
    if not valid:
        raise AlignmentDataError("Constructed alignment dataset failed its audit.")
    return {
        "schema_version": "contexttrace-requirement-alignment-audit-1.0",
        "valid": True,
        "source_cases": len(case_records),
        "examples": len(examples),
        "source_label_counts": dict(
            sorted(Counter(row["source_label"] for row in case_records).items())
        ),
        "case_split_counts": dict(
            sorted(Counter(row["split"] for row in case_records).items())
        ),
        "example_split_counts": dict(
            sorted(Counter(str(row["split"]) for row in examples).items())
        ),
        "task_counts": dict(
            sorted(Counter(str(row["task"]) for row in examples).items())
        ),
        "target_counts": dict(
            sorted(
                Counter(
                    "%s.%s" % (row["task"], row["target"]["label"])
                    for row in examples
                ).items()
            )
        ),
        "construction_counts": dict(
            sorted(
                Counter(str(row["source"]["construction"]) for row in examples).items()
            )
        ),
        "exclusions": exclusions,
        "integrity": {
            "unique_example_ids": True,
            "case_split_overlap": False,
            "normalized_claim_split_overlap": False,
            "evaluation_claim_overlap": overlap,
            "exact_requirement_spans": exact_requirements,
            "drop_one_removed_context_absent": drop_one_valid,
            "training_targets_absent_from_model_inputs": not inputs_contain_targets,
            "development_or_heldout_examples_used": False,
            "remote_inference_used": False,
        },
        "limitations": [
            "Requirement positives inherit WiCE's claim-level complete-support annotation.",
            "Synthetic drop-one negatives can be noisy when evidence sentences are redundant.",
            "Unannotated same-document sentences can contain unrecorded support.",
            "Partial-support annotations identify incomplete claim coverage, not the missing requirement.",
        ],
    }


def _eligible_cases(
    rows: list[dict[str, Any]], *, excluded_claims: set[str]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    eligible = []
    seen_claims = set()
    exclusions = Counter()
    for row in sorted(rows, key=_case_id):
        label = str(row.get("label") or "")
        claim = " ".join(str(row.get("claim") or "").split()).strip()
        claim_hash = _text_hash(claim)
        groups = _valid_groups(row)
        if label not in SOURCE_LABELS:
            exclusions["unsupported_source_label"] += 1
        elif not claim or not groups:
            exclusions["missing_claim_or_support_group"] += 1
        elif claim_hash in excluded_claims:
            exclusions["evaluation_claim_overlap"] += 1
        elif claim_hash in seen_claims:
            exclusions["duplicate_normalized_claim"] += 1
        else:
            seen_claims.add(claim_hash)
            eligible.append(row)
    return eligible, dict(sorted(exclusions.items()))


def _case_splits(
    rows: list[dict[str, Any]], *, validation_fraction: float, seed: int
) -> dict[str, str]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[str(row["label"])].append(row)
    output = {}
    for label, values in sorted(by_label.items()):
        ordered = sorted(
            values,
            key=lambda row: hashlib.sha256(
                ("%s:%s:%s" % (seed, label, _case_id(row))).encode("utf-8")
            ).hexdigest(),
        )
        validation_count = max(1, round(len(ordered) * validation_fraction))
        for index, row in enumerate(ordered):
            output[_case_id(row)] = (
                "internal_validation" if index < validation_count else "training"
            )
    return output


def _case_examples(
    row: dict[str, Any], *, split: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = _case_id(row)
    label = str(row["label"])
    claim = " ".join(str(row["claim"]).split())
    evidence = [str(value) for value in row["evidence"]]
    groups = _valid_groups(row)
    canonical = min(groups, key=lambda value: (len(value), tuple(value)))
    context_ids = [_context_id(case_id, index) for index in canonical]
    group_evidence = [
        {"id": context_id, "text": evidence[index]}
        for context_id, index in zip(context_ids, canonical, strict=True)
    ]
    requirements = requirement_spans(claim)
    if not requirements:
        raise AlignmentDataError("Eligible case produced no exact requirements.")
    examples = []
    if label == "supported":
        examples.append(
            _example(
                case_id=case_id,
                split=split,
                task="claim_group_completeness",
                label="complete",
                claim=claim,
                requirement=None,
                evidence=group_evidence,
                construction="gold_complete_group",
                source_label=label,
                group_indexes=canonical,
            )
        )
        for requirement in requirements:
            examples.append(
                _example(
                    case_id=case_id,
                    split=split,
                    task="requirement_alignment",
                    label="covered",
                    claim=claim,
                    requirement=requirement,
                    evidence=group_evidence,
                    construction="gold_complete_group",
                    source_label=label,
                    group_indexes=canonical,
                )
            )
        if len(canonical) > 1:
            removed = _most_material_index(claim, canonical, evidence)
            retained = [index for index in canonical if index != removed]
            examples.append(
                _example(
                    case_id=case_id,
                    split=split,
                    task="claim_group_completeness",
                    label="incomplete",
                    claim=claim,
                    requirement=None,
                    evidence=[
                        {"id": _context_id(case_id, index), "text": evidence[index]}
                        for index in retained
                    ],
                    construction="synthetic_drop_one",
                    source_label=label,
                    group_indexes=retained,
                    removed_context_ids=[_context_id(case_id, removed)],
                )
            )
        distractors = _hard_distractors(
            claim,
            evidence,
            excluded_indexes={index for group in groups for index in group},
            limit=max(1, min(3, len(canonical))),
        )
        if distractors:
            hard_evidence = [
                {"id": _context_id(case_id, index), "text": evidence[index]}
                for index in distractors
            ]
            examples.append(
                _example(
                    case_id=case_id,
                    split=split,
                    task="claim_group_completeness",
                    label="incomplete",
                    claim=claim,
                    requirement=None,
                    evidence=hard_evidence,
                    construction="same_document_hard_negative",
                    source_label=label,
                    group_indexes=distractors,
                )
            )
            for requirement in requirements:
                examples.append(
                    _example(
                        case_id=case_id,
                        split=split,
                        task="requirement_alignment",
                        label="missing",
                        claim=claim,
                        requirement=requirement,
                        evidence=hard_evidence,
                        construction="same_document_hard_negative",
                        source_label=label,
                        group_indexes=distractors,
                    )
                )
    else:
        examples.append(
            _example(
                case_id=case_id,
                split=split,
                task="claim_group_completeness",
                label="incomplete",
                claim=claim,
                requirement=None,
                evidence=group_evidence,
                construction="gold_partial_group",
                source_label=label,
                group_indexes=canonical,
            )
        )
    return examples, {
        "case_id": case_id,
        "split": split,
        "source_label": label,
        "requirements": len(requirements),
        "support_groups": len(groups),
    }


def _example(
    *,
    case_id: str,
    split: str,
    task: str,
    label: str,
    claim: str,
    requirement: dict[str, Any] | None,
    evidence: list[dict[str, str]],
    construction: str,
    source_label: str,
    group_indexes: list[int],
    removed_context_ids: list[str] | None = None,
) -> dict[str, Any]:
    requirement_id = str((requirement or {}).get("id") or "claim")
    identifier = "%s:%s:%s:%s" % (case_id, task, construction, requirement_id)
    source = {
        "dataset": "WiCE",
        "source_split": "train",
        "case_id": case_id,
        "source_label": source_label,
        "construction": construction,
        "supporting_sentence_indexes": list(group_indexes),
        "label_provenance": _label_provenance(construction),
    }
    if removed_context_ids:
        source["removed_context_ids"] = list(removed_context_ids)
    return {
        "id": identifier,
        "split": split,
        "task": task,
        "input": {
            "claim": claim,
            "requirement": dict(requirement) if requirement else None,
            "evidence": evidence,
        },
        "target": {"label": label},
        "source": source,
    }


def _label_provenance(construction: str) -> dict[str, Any]:
    if construction == "gold_complete_group":
        return {
            "kind": "upstream_human_label",
            "strength": "strong_claim_level_inherited_for_requirements",
        }
    if construction == "gold_partial_group":
        return {
            "kind": "upstream_human_label",
            "strength": "strong_claim_level",
        }
    if construction == "synthetic_drop_one":
        return {
            "kind": "deterministic_counterfactual",
            "strength": "weak_possible_redundancy",
        }
    return {
        "kind": "upstream_annotation_exclusion",
        "strength": "weak_possible_unannotated_support",
    }


def _valid_groups(row: dict[str, Any]) -> list[list[int]]:
    evidence = row.get("evidence") or []
    output = []
    seen = set()
    for raw_group in row.get("supporting_sentences") or []:
        if not isinstance(raw_group, list):
            continue
        group = sorted(
            {
                index
                for index in raw_group
                if isinstance(index, int)
                and 0 <= index < len(evidence)
                and str(evidence[index]).strip()
            }
        )
        key = tuple(group)
        if group and key not in seen:
            seen.add(key)
            output.append(group)
    return output


def _most_material_index(claim: str, indexes: list[int], evidence: list[str]) -> int:
    claim_tokens = _content_tokens(claim)
    ranked = []
    for index in indexes:
        other_tokens = _content_tokens(
            " ".join(evidence[other] for other in indexes if other != index)
        )
        unique_coverage = len((claim_tokens & _content_tokens(evidence[index])) - other_tokens)
        ranked.append((unique_coverage, _stable_rank("drop", str(index), evidence[index]), index))
    return max(ranked)[2]


def _hard_distractors(
    claim: str,
    evidence: list[str],
    *,
    excluded_indexes: set[int],
    limit: int,
) -> list[int]:
    claim_tokens = _content_tokens(claim)
    candidates = []
    for index, text in enumerate(evidence):
        if index in excluded_indexes or not str(text).strip():
            continue
        tokens = _content_tokens(text)
        overlap = len(claim_tokens & tokens) / len(claim_tokens) if claim_tokens else 0.0
        candidates.append((overlap, _stable_rank("hard", str(index), text), index))
    return [row[2] for row in sorted(candidates, reverse=True)[:limit]]


def load_excluded_claims(paths: list[str | Path]) -> tuple[set[str], list[dict[str, Any]]]:
    claims = set()
    records = []
    for value in paths:
        path = Path(value)
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload.get("cases") or []
        for case in cases:
            claims.add(_text_hash(str(case.get("claim") or "")))
        records.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "cases": len(cases),
            }
        )
    return claims, records


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).casefold())
        if len(token) >= 2 and token not in CONTENT_STOPWORDS
    }


def _context_id(case_id: str, index: int) -> str:
    return "%s_e%04d" % (case_id, index)


def _case_id(row: dict[str, Any]) -> str:
    source_id = str((row.get("meta") or {}).get("id") or "").strip()
    if not source_id:
        raise AlignmentDataError("WiCE row has no source id.")
    return "wice_%s" % source_id


def _stable_rank(*values: str) -> str:
    return hashlib.sha256(":".join(values).encode("utf-8")).hexdigest()


def _text_hash(value: str) -> str:
    normalized = " ".join(str(value).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--exclude-case-pack", action="append", default=[])
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)

    source = Path(args.source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != TRAIN_SHA256:
        raise AlignmentDataError("WiCE train source hash does not match the pinned artifact.")
    excluded_claims, exclusion_records = load_excluded_claims(args.exclude_case_pack)
    dataset, audit = build_dataset(
        _read_jsonl(source),
        excluded_claims=excluded_claims,
    )
    audit["source"] = {
        "path": str(source),
        "sha256": source_hash,
        "bytes": source.stat().st_size,
    }
    audit["evaluation_exclusion_packs"] = exclusion_records
    dataset_output = Path(args.dataset_output)
    audit_output = Path(args.audit_output)
    _write(dataset_output, dataset)
    _write(audit_output, audit)
    builder_path = Path(__file__)
    manifest = {
        "schema_version": "contexttrace-requirement-alignment-manifest-1.0",
        "source": {"url": TRAIN_URL, "sha256": source_hash},
        "artifacts": [
            {
                "path": _portable_path(dataset_output),
                "bytes": dataset_output.stat().st_size,
                "sha256": hashlib.sha256(dataset_output.read_bytes()).hexdigest(),
            },
            {
                "path": _portable_path(audit_output),
                "bytes": audit_output.stat().st_size,
                "sha256": hashlib.sha256(audit_output.read_bytes()).hexdigest(),
            },
            {
                "path": _portable_path(builder_path),
                "bytes": builder_path.stat().st_size,
                "sha256": hashlib.sha256(builder_path.read_bytes()).hexdigest(),
            },
        ],
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "development_or_heldout_examples_used": False,
    }
    _write(Path(args.manifest_output), manifest)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
