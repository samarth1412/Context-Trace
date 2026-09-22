"""Build a direct, human-labeled requirement-alignment development set."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SOURCE_ZIP_SHA256 = "e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b"
SOURCE_MEMBER = "contract-nli/dev.json"
SOURCE_MEMBER_SHA256 = "310af7d661d2ab50ee3700169cef524c75f39fb296bbf5a515c229eb0f42e68e"
SEED = 20260928
CASES_PER_RELATION = 80
MAX_EVIDENCE_WORDS = 180
MAX_RETRIEVED_SPANS = 3
RELATION_TARGET = {
    "Entailment": "covered",
    "Contradiction": "missing",
    "NotMentioned": "missing",
}
STOPWORDS = {
    "a",
    "all",
    "an",
    "and",
    "are",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "may",
    "of",
    "or",
    "shall",
    "some",
    "that",
    "the",
    "to",
    "with",
}


class DevelopmentDataError(RuntimeError):
    """Raised when the development-set provenance contract is violated."""


def build_development_set(
    payload: dict[str, Any],
    *,
    cases_per_relation: int = CASES_PER_RELATION,
    seed: int = SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if cases_per_relation < 1:
        raise DevelopmentDataError("cases_per_relation must be positive.")
    labels = payload.get("labels") or {}
    documents = payload.get("documents") or []
    if not isinstance(labels, dict) or not labels or not isinstance(documents, list):
        raise DevelopmentDataError("ContractNLI payload is missing labels or documents.")

    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exclusions = Counter()
    for document in documents:
        annotations = _annotations(document)
        for hypothesis_id, annotation in sorted(annotations.items()):
            relation = str(annotation.get("choice") or "")
            if relation not in RELATION_TARGET or hypothesis_id not in labels:
                exclusions["unknown_relation_or_hypothesis"] += 1
                continue
            hypothesis = " ".join(
                str(labels[hypothesis_id].get("hypothesis") or "").split()
            )
            if not hypothesis:
                exclusions["empty_hypothesis"] += 1
                continue
            evidence, evidence_indexes, selection = _selected_evidence(
                document,
                hypothesis=hypothesis,
                relation=relation,
                annotated_indexes=annotation.get("spans") or [],
                source_split="dev",
            )
            if not evidence:
                exclusions["no_evidence_within_budget"] += 1
                continue
            candidates[relation].append(
                _example(
                    document=document,
                    hypothesis_id=hypothesis_id,
                    hypothesis=hypothesis,
                    description=str(labels[hypothesis_id].get("short_description") or ""),
                    relation=relation,
                    evidence=evidence,
                    evidence_indexes=evidence_indexes,
                    evidence_selection=selection,
                    source_split="dev",
                )
            )

    selected = []
    for relation in RELATION_TARGET:
        relation_rows = candidates.get(relation) or []
        if len(relation_rows) < cases_per_relation:
            raise DevelopmentDataError(
                "%s has only %d eligible cases; %d required."
                % (relation, len(relation_rows), cases_per_relation)
            )
        selected.extend(
            _round_robin_sample(
                relation_rows,
                size=cases_per_relation,
                seed=seed,
                relation=relation,
            )
        )
    examples = sorted(selected, key=lambda row: str(row["id"]))
    dataset = {
        "schema_version": "contexttrace-requirement-development-1.0",
        "dataset": "ContractNLI direct requirement alignment development",
        "source": {
            "dataset": "ContractNLI",
            "split": "dev",
            "archive_sha256": SOURCE_ZIP_SHA256,
            "member": SOURCE_MEMBER,
            "member_sha256": SOURCE_MEMBER_SHA256,
            "license": "CC BY 4.0",
        },
        "construction": {
            "seed": seed,
            "cases_per_relation": cases_per_relation,
            "balanced_relations": list(RELATION_TARGET),
            "max_evidence_words": MAX_EVIDENCE_WORDS,
            "max_retrieved_spans": MAX_RETRIEVED_SPANS,
            "annotated_spans_only_for_entailment_and_contradiction": True,
            "deterministic_lexical_spans_for_not_mentioned": True,
            "test_split_accessed": False,
            "model_or_api_labels_used": False,
        },
        "examples": examples,
    }
    audit = audit_development_set(
        dataset,
        source_documents=len(documents),
        candidate_counts={key: len(value) for key, value in candidates.items()},
        exclusions=dict(sorted(exclusions.items())),
    )
    return dataset, audit


def audit_development_set(
    dataset: dict[str, Any],
    *,
    source_documents: int,
    candidate_counts: dict[str, int],
    exclusions: dict[str, int],
) -> dict[str, Any]:
    examples = list(dataset.get("examples") or [])
    ids = [str(row.get("id") or "") for row in examples]
    relation_counts = Counter(str(row["source"]["relation"]) for row in examples)
    target_counts = Counter(str(row["target"]["label"]) for row in examples)
    input_has_target = any(
        any(key in row["input"] for key in ("label", "target", "relation"))
        for row in examples
    )
    exact_spans = all(
        row["input"]["claim"][
            row["input"]["requirement"]["start_char"] : row["input"]["requirement"][
                "end_char"
            ]
        ]
        == row["input"]["requirement"]["text"]
        for row in examples
    )
    within_budget = all(
        sum(len(item["text"].split()) for item in row["input"]["evidence"])
        <= MAX_EVIDENCE_WORDS
        for row in examples
    )
    annotated_relations_valid = all(
        row["source"]["evidence_selection"] == "upstream_annotated_spans"
        for row in examples
        if row["source"]["relation"] in {"Entailment", "Contradiction"}
    )
    balanced = len(set(relation_counts.values())) == 1 and set(relation_counts) == set(
        RELATION_TARGET
    )
    valid = bool(
        examples
        and len(ids) == len(set(ids))
        and balanced
        and exact_spans
        and within_budget
        and annotated_relations_valid
        and not input_has_target
    )
    if not valid:
        raise DevelopmentDataError("Constructed development set failed its audit.")
    return {
        "schema_version": "contexttrace-requirement-development-audit-1.0",
        "valid": True,
        "source_documents": source_documents,
        "selected_documents": len(
            {str(row["source"]["document_id"]) for row in examples}
        ),
        "examples": len(examples),
        "candidate_counts": dict(sorted(candidate_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "target_counts": dict(sorted(target_counts.items())),
        "hypotheses": len(
            {str(row["source"]["hypothesis_id"]) for row in examples}
        ),
        "evidence_selection_counts": dict(
            sorted(
                Counter(
                    str(row["source"]["evidence_selection"]) for row in examples
                ).items()
            )
        ),
        "exclusions": exclusions,
        "integrity": {
            "unique_example_ids": True,
            "balanced_relations": balanced,
            "exact_requirement_spans": exact_spans,
            "evidence_within_word_budget": within_budget,
            "annotated_evidence_for_labeled_relations": annotated_relations_valid,
            "targets_absent_from_model_inputs": not input_has_target,
            "model_or_api_labels_used": False,
            "test_split_accessed": False,
        },
        "limitations": [
            "The development set is legal-domain data with 17 repeated hypotheses.",
            "NotMentioned cases require deterministic retrieval because no gold evidence span exists.",
            "Claim and requirement text are identical because each ContractNLI hypothesis is one direct requirement.",
            "This is development data and must not be presented as untouched confirmation evidence.",
        ],
    }


def _annotations(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sets = document.get("annotation_sets") or []
    if len(sets) != 1 or not isinstance(sets[0].get("annotations"), dict):
        raise DevelopmentDataError("Expected one ContractNLI annotation set per document.")
    return sets[0]["annotations"]


def _selected_evidence(
    document: dict[str, Any],
    *,
    hypothesis: str,
    relation: str,
    annotated_indexes: list[Any],
    source_split: str = "dev",
) -> tuple[list[dict[str, str]], list[int], str]:
    text = str(document.get("text") or "")
    spans = document.get("spans") or []
    document_id = str(document.get("id") or "")
    if relation in {"Entailment", "Contradiction"}:
        indexes = sorted(
            {
                index
                for index in annotated_indexes
                if isinstance(index, int) and 0 <= index < len(spans)
            }
        )
        evidence = _span_evidence(
            text,
            spans,
            indexes,
            document_id=document_id,
            source_split=source_split,
        )
        if sum(len(item["text"].split()) for item in evidence) > MAX_EVIDENCE_WORDS:
            return [], [], "upstream_annotated_spans"
        return evidence, indexes, "upstream_annotated_spans"

    hypothesis_tokens = _content_tokens(hypothesis)
    ranked = []
    for index in range(len(spans)):
        evidence = _span_evidence(
            text,
            spans,
            [index],
            document_id=document_id,
            source_split=source_split,
        )
        if not evidence:
            continue
        span_text = evidence[0]["text"]
        words = len(span_text.split())
        if words > MAX_EVIDENCE_WORDS:
            continue
        overlap = len(hypothesis_tokens & _content_tokens(span_text))
        ranked.append(
            (
                overlap,
                _stable_rank(str(document_id), str(index), hypothesis),
                index,
                words,
            )
        )
    chosen = []
    word_count = 0
    for _, _, index, words in sorted(ranked, reverse=True):
        if len(chosen) >= MAX_RETRIEVED_SPANS:
            break
        if word_count + words <= MAX_EVIDENCE_WORDS:
            chosen.append(index)
            word_count += words
    chosen.sort()
    return (
        _span_evidence(
            text,
            spans,
            chosen,
            document_id=document_id,
            source_split=source_split,
        ),
        chosen,
        "deterministic_lexical_retrieval",
    )


def _span_evidence(
    text: str,
    spans: list[Any],
    indexes: list[int],
    *,
    document_id: str,
    source_split: str = "dev",
) -> list[dict[str, str]]:
    output = []
    for index in indexes:
        raw = spans[index]
        if not isinstance(raw, list) or len(raw) != 2:
            continue
        start, end = int(raw[0]), int(raw[1])
        value = " ".join(text[start:end].split()).strip()
        if value:
            output.append(
                {
                    "id": "contractnli_%s_%s_s%04d"
                    % (source_split, document_id, index),
                    "text": value,
                }
            )
    return output


def _example(
    *,
    document: dict[str, Any],
    hypothesis_id: str,
    hypothesis: str,
    description: str,
    relation: str,
    evidence: list[dict[str, str]],
    evidence_indexes: list[int],
    evidence_selection: str,
    source_split: str = "dev",
) -> dict[str, Any]:
    document_id = str(document.get("id") or "")
    return {
        "id": "contractnli_%s_%s_%s"
        % (source_split, document_id, hypothesis_id),
        "split": "development",
        "task": "requirement_alignment",
        "input": {
            "claim": hypothesis,
            "requirement": {
                "id": "r00",
                "text": hypothesis,
                "start_char": 0,
                "end_char": len(hypothesis),
            },
            "evidence": evidence,
        },
        "target": {"label": RELATION_TARGET[relation]},
        "source": {
            "dataset": "ContractNLI",
            "source_split": source_split,
            "document_id": document_id,
            "hypothesis_id": hypothesis_id,
            "hypothesis_description": description,
            "relation": relation,
            "evidence_selection": evidence_selection,
            "evidence_span_indexes": evidence_indexes,
            "label_provenance": {
                "kind": "upstream_human_nli_label",
                "strength": "direct_requirement_label",
            },
        },
    }


def _round_robin_sample(
    rows: list[dict[str, Any]], *, size: int, seed: int, relation: str
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source"]["hypothesis_id"])].append(row)
    for hypothesis_id, values in grouped.items():
        values.sort(
            key=lambda row: _stable_rank(
                str(seed), relation, hypothesis_id, str(row["source"]["document_id"])
            )
        )
    hypothesis_ids = sorted(
        grouped,
        key=lambda value: _stable_rank(str(seed), relation, value),
    )
    output = []
    while len(output) < size:
        progressed = False
        for hypothesis_id in hypothesis_ids:
            if grouped[hypothesis_id] and len(output) < size:
                output.append(grouped[hypothesis_id].pop(0))
                progressed = True
        if not progressed:
            break
    return output


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) >= 2 and token not in STOPWORDS
    }


def _stable_rank(*values: str) -> str:
    return hashlib.sha256(":".join(values).encode()).hexdigest()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", required=True)
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--cases-per-relation", type=int, default=CASES_PER_RELATION)
    args = parser.parse_args(argv)

    source = Path(args.source_zip)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_ZIP_SHA256:
        raise DevelopmentDataError("ContractNLI archive does not match its pin.")
    with zipfile.ZipFile(source) as archive:
        raw = archive.read(SOURCE_MEMBER)
    if hashlib.sha256(raw).hexdigest() != SOURCE_MEMBER_SHA256:
        raise DevelopmentDataError("ContractNLI development member does not match its pin.")
    dataset, audit = build_development_set(
        json.loads(raw), cases_per_relation=args.cases_per_relation
    )
    dataset_path = Path(args.dataset_output)
    audit_path = Path(args.audit_output)
    _write(dataset_path, dataset)
    _write(audit_path, audit)
    manifest = {
        "schema_version": "contexttrace-requirement-development-manifest-1.0",
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "source_archive_sha256": SOURCE_ZIP_SHA256,
        "source_member": SOURCE_MEMBER,
        "source_member_sha256": SOURCE_MEMBER_SHA256,
        "examples": audit["examples"],
        "test_split_accessed": False,
    }
    _write(Path(args.manifest_output), manifest)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
