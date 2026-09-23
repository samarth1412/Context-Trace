"""Build a frozen cross-domain SciFact transfer evaluation for the v6 cascade."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DATASET_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
ARCHIVE_SHA256 = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"
TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
RELATIONS = ("Entailment", "Contradiction", "NotMentioned")


class V7BuildError(RuntimeError):
    """Raised when the SciFact source or frozen split contract is invalid."""


def build(
    source_dir: str | Path,
    *,
    source_archive: str | Path,
    development_per_relation: int = 90,
    evaluation_per_relation: int = 60,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = Path(source_dir)
    archive = Path(source_archive)
    required = {
        "corpus": source / "corpus.jsonl",
        "train": source / "claims_train.jsonl",
        "dev": source / "claims_dev.jsonl",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise V7BuildError("Missing SciFact source files: %s" % ", ".join(missing))
    if not archive.is_file() or _sha256(archive) != ARCHIVE_SHA256:
        raise V7BuildError("SciFact archive does not match the frozen SHA-256.")
    if development_per_relation < 1 or evaluation_per_relation < 1:
        raise V7BuildError("Per-relation sample sizes must be positive.")

    corpus = {
        int(row["doc_id"]): row for row in _read_jsonl(required["corpus"])
    }
    development = _build_split(
        _read_jsonl(required["train"]),
        corpus,
        source_split="train",
        output_split="scifact_development",
        per_relation=development_per_relation,
    )
    evaluation = _build_split(
        _read_jsonl(required["dev"]),
        corpus,
        source_split="dev",
        output_split="scifact_evaluation",
        per_relation=evaluation_per_relation,
    )
    development_ids = {row["id"] for row in development}
    evaluation_ids = {row["id"] for row in evaluation}
    development_claims = {row["source"]["claim_id"] for row in development}
    evaluation_claims = {row["source"]["claim_id"] for row in evaluation}
    if development_ids & evaluation_ids or development_claims & evaluation_claims:
        raise V7BuildError("Development and evaluation examples must be disjoint.")

    source_record = {
        "dataset": "SciFact",
        "upstream_repository": "https://github.com/allenai/scifact",
        "download_url": DATASET_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "licenses": {
            "claims_and_annotations": "CC BY 4.0",
            "abstracts": "ODC-By 1.0",
        },
        "files": {
            name: {"path": path.name, "sha256": _sha256(path)}
            for name, path in required.items()
        },
    }
    development_payload = _dataset_payload(
        development, split="scifact_development", source=source_record
    )
    evaluation_payload = _dataset_payload(
        evaluation, split="scifact_evaluation", source=source_record
    )
    audit = {
        "schema_version": "contexttrace-scifact-v7-audit-1.0",
        "experiment": "contexttrace_v7_scifact_transfer",
        "source": source_record,
        "selection": {
            "algorithm": "sha256_order_v1",
            "seed_material": "contexttrace-scifact-v7|source_split|relation|claim_id",
            "label_balancing_only": True,
            "model_outputs_used": False,
            "development_per_relation": development_per_relation,
            "evaluation_per_relation": evaluation_per_relation,
        },
        "development": _split_audit(development),
        "evaluation": _split_audit(evaluation),
        "checks": {
            "case_ids_disjoint": not bool(development_ids & evaluation_ids),
            "claim_ids_disjoint": not bool(development_claims & evaluation_claims),
            "labels_absent_from_inputs": all(
                not ({"label", "target", "relation"} & set(row["input"]))
                for row in development + evaluation
            ),
            "evaluation_uses_upstream_dev_only": all(
                row["source"]["source_split"] == "dev" for row in evaluation
            ),
            "development_uses_upstream_train_only": all(
                row["source"]["source_split"] == "train" for row in development
            ),
            "synthetic_labels_used": False,
        },
        "limitations": [
            "SciFact's public dev split is used as evaluation because public test labels are unavailable.",
            "The task covers support, contradiction, and no-evidence cases; it does not provide partial-support or ambiguity labels.",
            "Gold rationale sentences isolate verification quality from retrieval quality.",
            "No-evidence cases use deterministic high-overlap sentence selection from cited abstracts with no annotated evidence.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-scifact-v7-manifest-1.0",
        "experiment": "contexttrace_v7_scifact_transfer",
        "status": "frozen_before_model_scoring",
        "source_archive_sha256": ARCHIVE_SHA256,
        "development_sha256": _sha256_json(development_payload),
        "evaluation_sha256": _sha256_json(evaluation_payload),
        "audit_sha256": _sha256_json(audit),
        "frozen_v6_policy": "benchmarks/requirement_alignment/results/v6_cascade_policy.json",
        "policy_selection_uses_scifact": False,
        "evaluation_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return development_payload, evaluation_payload, audit, manifest


def _build_split(
    claims: list[dict[str, Any]],
    corpus: dict[int, dict[str, Any]],
    *,
    source_split: str,
    output_split: str,
    per_relation: int,
) -> list[dict[str, Any]]:
    candidates: dict[str, list[dict[str, Any]]] = {relation: [] for relation in RELATIONS}
    for claim in claims:
        evidence = claim.get("evidence") or {}
        labels = {
            str(group["label"])
            for groups in evidence.values()
            for group in groups
        }
        if len(labels) > 1:
            raise V7BuildError("SciFact claim %s has mixed evidence labels." % claim["id"])
        if labels:
            upstream = labels.pop()
            relation = "Entailment" if upstream == "SUPPORT" else "Contradiction"
            candidates[relation].append(
                _labeled_example(
                    claim,
                    corpus,
                    relation=relation,
                    source_split=source_split,
                    output_split=output_split,
                )
            )
        elif claim.get("cited_doc_ids"):
            candidates["NotMentioned"].append(
                _missing_example(
                    claim,
                    corpus,
                    source_split=source_split,
                    output_split=output_split,
                )
            )

    selected: list[dict[str, Any]] = []
    for relation in RELATIONS:
        rows = sorted(
            candidates[relation],
            key=lambda row: hashlib.sha256(
                (
                    "contexttrace-scifact-v7|%s|%s|%s"
                    % (source_split, relation, row["source"]["claim_id"])
                ).encode("utf-8")
            ).hexdigest(),
        )
        if len(rows) < per_relation:
            raise V7BuildError(
                "%s has %d %s candidates; %d required."
                % (source_split, len(rows), relation, per_relation)
            )
        selected.extend(rows[:per_relation])
    return sorted(selected, key=lambda row: row["id"])


def _labeled_example(
    claim: dict[str, Any],
    corpus: dict[int, dict[str, Any]],
    *,
    relation: str,
    source_split: str,
    output_split: str,
) -> dict[str, Any]:
    choices: list[tuple[int, tuple[int, ...]]] = []
    for raw_doc_id, groups in (claim.get("evidence") or {}).items():
        for group in groups:
            choices.append((int(raw_doc_id), tuple(int(value) for value in group["sentences"])))
    if not choices:
        raise V7BuildError("Labeled claim has no rationale sentences.")
    doc_id, sentence_ids = min(choices, key=lambda value: (value[0], value[1]))
    document = corpus.get(doc_id)
    if document is None:
        raise V7BuildError("SciFact corpus is missing document %s." % doc_id)
    abstract = list(document.get("abstract") or [])
    evidence = []
    for sentence_id in sentence_ids:
        if not 0 <= sentence_id < len(abstract):
            raise V7BuildError("SciFact rationale index is outside its abstract.")
        evidence.append(
            {
                "id": "scifact_%s_doc%s_s%04d" % (source_split, doc_id, sentence_id),
                "text": str(abstract[sentence_id]),
            }
        )
    return _example(
        claim,
        document,
        evidence,
        relation=relation,
        source_split=source_split,
        output_split=output_split,
        evidence_selection="upstream_gold_rationale",
        sentence_ids=list(sentence_ids),
    )


def _missing_example(
    claim: dict[str, Any],
    corpus: dict[int, dict[str, Any]],
    *,
    source_split: str,
    output_split: str,
) -> dict[str, Any]:
    if claim.get("evidence"):
        raise V7BuildError("NotMentioned examples must have no annotated evidence.")
    claim_tokens = _tokens(str(claim["claim"]))
    documents = []
    for raw_doc_id in claim.get("cited_doc_ids") or []:
        doc_id = int(raw_doc_id)
        document = corpus.get(doc_id)
        if document is None:
            raise V7BuildError("SciFact corpus is missing cited document %s." % doc_id)
        score = sum(len(claim_tokens & _tokens(str(sentence))) for sentence in document["abstract"])
        documents.append((-score, doc_id, document))
    if not documents:
        raise V7BuildError("No-evidence claim has no cited documents.")
    _, doc_id, document = min(documents, key=lambda value: (value[0], value[1]))
    ranked = sorted(
        enumerate(document["abstract"]),
        key=lambda value: (
            -len(claim_tokens & _tokens(str(value[1]))),
            value[0],
        ),
    )[:3]
    sentence_ids = sorted(index for index, _ in ranked)
    evidence = [
        {
            "id": "scifact_%s_doc%s_s%04d" % (source_split, doc_id, sentence_id),
            "text": str(document["abstract"][sentence_id]),
        }
        for sentence_id in sentence_ids
    ]
    return _example(
        claim,
        document,
        evidence,
        relation="NotMentioned",
        source_split=source_split,
        output_split=output_split,
        evidence_selection="deterministic_high_overlap_from_no_evidence_cited_abstract",
        sentence_ids=sentence_ids,
    )


def _example(
    claim: dict[str, Any],
    document: dict[str, Any],
    evidence: list[dict[str, str]],
    *,
    relation: str,
    source_split: str,
    output_split: str,
    evidence_selection: str,
    sentence_ids: list[int],
) -> dict[str, Any]:
    claim_text = str(claim["claim"])
    doc_id = int(document["doc_id"])
    claim_id = int(claim["id"])
    return {
        "id": "scifact_%s_%s_%s" % (source_split, claim_id, relation.lower()),
        "task": "cross_domain_claim_verification",
        "split": output_split,
        "input": {
            "claim": claim_text,
            "requirement": {
                "id": "r00",
                "text": claim_text,
                "start_char": 0,
                "end_char": len(claim_text),
            },
            "evidence": evidence,
        },
        "target": {"label": "covered" if relation == "Entailment" else "missing"},
        "source": {
            "dataset": "SciFact",
            "source_split": source_split,
            "claim_id": claim_id,
            "document_id": doc_id,
            "document_title": str(document.get("title") or ""),
            "relation": relation,
            "evidence_selection": evidence_selection,
            "evidence_sentence_indexes": sentence_ids,
            "label_provenance": {
                "kind": "upstream_expert_scifact_annotation",
                "synthetic": False,
            },
        },
    }


def _dataset_payload(
    examples: list[dict[str, Any]], *, split: str, source: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "contexttrace-scifact-v7-dataset-1.0",
        "dataset": "ContextTrace-SciFact-v7",
        "experiment": "contexttrace_v7_scifact_transfer",
        "split": split,
        "source": source,
        "construction": {
            "balanced_relations": list(RELATIONS),
            "model_outputs_used": False,
            "synthetic_labels_used": False,
            "evaluation_labels_present_in_model_input": False,
        },
        "examples": examples,
    }


def _split_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    relation_counts = Counter(row["source"]["relation"] for row in rows)
    return {
        "cases": len(rows),
        "relations": dict(sorted(relation_counts.items())),
        "unique_claims": len({row["source"]["claim_id"] for row in rows}),
        "unique_documents": len({row["source"]["document_id"] for row in rows}),
        "evidence_sentences": sum(len(row["input"]["evidence"]) for row in rows),
    }


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(text)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise V7BuildError("Invalid JSON at %s:%d." % (path, line_number)) from error
            if not isinstance(value, dict):
                raise V7BuildError("Expected JSON objects in %s." % path)
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--source-archive", required=True)
    parser.add_argument("--development-output", required=True)
    parser.add_argument("--evaluation-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--development-per-relation", type=int, default=90)
    parser.add_argument("--evaluation-per-relation", type=int, default=60)
    args = parser.parse_args(argv)
    development, evaluation, audit, manifest = build(
        args.source_dir,
        source_archive=args.source_archive,
        development_per_relation=args.development_per_relation,
        evaluation_per_relation=args.evaluation_per_relation,
    )
    _write(Path(args.development_output), development)
    _write(Path(args.evaluation_output), evaluation)
    _write(Path(args.audit_output), audit)
    _write(Path(args.manifest_output), manifest)
    print(
        json.dumps(
            {
                "development_cases": len(development["examples"]),
                "evaluation_cases": len(evaluation["examples"]),
                "manifest": manifest,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
