"""Build a deterministic public-test confirmation set for all five verdicts."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from benchmarks.external_fiveway_confirmation.acquire import SOURCES, sha256


LABELS = (
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
)
WICE_LABELS = {
    "supported": "supported",
    "partially_supported": "partially_supported",
    "not_supported": "unsupported",
}
VITAMINC_MEMBER = "vitaminc/test.jsonl"
SEED = 20260921
PER_LABEL = 25


class AdapterError(ValueError):
    """Raised when a source cannot be mapped without changing label meaning."""


def build_case_pack(
    *,
    wice_path: str | Path,
    vitaminc_path: str | Path,
    ambient_path: str | Path,
    per_label: int = PER_LABEL,
    seed: int = SEED,
) -> dict[str, Any]:
    if per_label < 1:
        raise AdapterError("per_label must be positive.")
    paths = {
        "wice": Path(wice_path),
        "vitaminc": Path(vitaminc_path),
        "ambient": Path(ambient_path),
    }
    _require_source_hash(paths["wice"], "wice_test.jsonl")
    _require_source_hash(paths["vitaminc"], "vitaminc.zip")
    _require_source_hash(paths["ambient"], "ambient_test.jsonl")

    candidates = [
        *_wice_cases(paths["wice"]),
        *_vitaminc_cases(paths["vitaminc"]),
        *_ambient_cases(paths["ambient"]),
    ]
    selected = _balanced_sample(candidates, per_label=per_label, seed=seed)
    counts = Counter(str(row["expected_verdict"]) for row in selected)
    if counts != Counter({label: per_label for label in LABELS}):
        raise AdapterError("Could not produce the requested balanced five-label set: %r" % counts)
    return {
        "schema_version": "external-fiveway-confirmation-1.0",
        "dataset": "WiCE+VitaminC+AmbiEnt",
        "split": "heldout",
        "label_scope": "public_human_labels_aligned_to_contexttrace_claim_verdicts",
        "independent_source_labels": True,
        "predictions_used_for_selection": False,
        "selection": {
            "method": "stable_sha256_stratified_without_replacement",
            "seed": seed,
            "per_label": per_label,
            "vitaminc_real_revisions_only": True,
        },
        "label_mapping": {
            "WiCE.supported": "supported",
            "WiCE.partially_supported": "partially_supported",
            "WiCE.not_supported": "unsupported",
            "VitaminC.real.REFUTES": "contradicted",
            "AmbiEnt.multiple_plausible_NLI_labels": "unverifiable",
        },
        "label_mapping_exclusions": {
            "VitaminC.synthetic": "Excluded to keep the contradiction slice grounded in real revisions.",
            "single_label_NLI_neutral": (
                "Excluded because ordinary neutral/unknown does not establish ambiguity."
            ),
        },
        "evidence_regime": {
            "source": "complete upstream evidence segmented into source-provided spans",
            "selection": "ContextTrace label-blind shared local selector at evaluation time",
            "max_selected_spans": 8,
            "oracle_evidence_used_as_model_input": False,
            "upstream_evidence_annotations_retained_for_retrieval_diagnostics_only": True,
        },
        "sources": {
            "wice": _source_record(paths["wice"], "wice_test.jsonl"),
            "vitaminc": {
                **_source_record(paths["vitaminc"], "vitaminc.zip"),
                "archive_member": VITAMINC_MEMBER,
                "archive_member_sha256": _zip_member_sha256(paths["vitaminc"], VITAMINC_MEMBER),
            },
            "ambient": _source_record(paths["ambient"], "ambient_test.jsonl"),
        },
        "label_counts": dict(sorted(counts.items())),
        "limitations": [
            "This is public-test external validation, so model pretraining contamination cannot be ruled out.",
            "Labels were created for the upstream tasks and aligned conservatively; they are not native ContextTrace annotations.",
            "VitaminC real-revision labels are contrastively constructed upstream rather than newly annotated for ContextTrace.",
            "The benchmark jointly measures label-blind evidence selection and verification.",
            "AmbiEnt evaluates linguistic ambiguity in short NLI pairs rather than long-form RAG retrieval.",
        ],
        "cases": selected,
    }


def _wice_cases(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    cases = []
    seen = set()
    for index, row in enumerate(rows):
        upstream = str(row.get("label") or "")
        if upstream not in WICE_LABELS:
            raise AdapterError("Unknown WiCE label %r." % upstream)
        source_id = str((row.get("meta") or {}).get("id") or "row%05d" % index)
        case_id = "wice_%s" % source_id
        if case_id in seen:
            raise AdapterError("Duplicate WiCE id %s." % case_id)
        seen.add(case_id)
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            raise AdapterError("WiCE case %s has invalid evidence." % case_id)
        contexts = _contexts(
            ("%s_e%04d" % (case_id, evidence_index), text)
            for evidence_index, text in enumerate(evidence)
        )
        if not contexts:
            raise AdapterError("WiCE case %s has no evidence text." % case_id)
        supporting = row.get("supporting_sentences") or []
        annotated_ids = sorted(
            {
                "%s_e%04d" % (case_id, int(sentence_index))
                for group in supporting
                if isinstance(group, list)
                for sentence_index in group
                if isinstance(sentence_index, int) and 0 <= sentence_index < len(evidence)
            }
        )
        cases.append(
            {
                "id": case_id,
                "dataset": "WiCE",
                "source_split": "test",
                "label_scope": "natural_wikipedia_claim",
                "query": "",
                "claim": str(row.get("claim") or "").strip(),
                "contexts": contexts,
                "expected_verdict": WICE_LABELS[upstream],
                "upstream_label": upstream,
                "upstream_evidence_context_ids": annotated_ids,
            }
        )
    return cases


def _vitaminc_cases(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        rows = [
            json.loads(line)
            for line in archive.read(VITAMINC_MEMBER).splitlines()
            if line.strip()
        ]
    cases = []
    for row in rows:
        if row.get("label") != "REFUTES" or row.get("revision_type") != "real":
            continue
        source_id = str(row.get("unique_id") or "").strip()
        claim = str(row.get("claim") or "").strip()
        evidence = str(row.get("evidence") or "").strip()
        if not source_id or not claim or not evidence:
            raise AdapterError("VitaminC real-refutes row is incomplete.")
        case_id = "vitaminc_%s" % source_id
        context_id = "%s_evidence" % case_id
        cases.append(
            {
                "id": case_id,
                "dataset": "VitaminC",
                "source_split": "test",
                "label_scope": "real_wikipedia_revision_claim_evidence_pair",
                "query": "",
                "claim": claim,
                "contexts": [{"id": context_id, "text": evidence}],
                "expected_verdict": "contradicted",
                "upstream_label": "REFUTES",
                "upstream_revision_type": "real",
                "upstream_case_id": str(row.get("case_id") or ""),
                "upstream_evidence_context_ids": [context_id],
            }
        )
    return cases


def _ambient_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for row in _read_jsonl(path):
        labels = _ambient_labels(row.get("labels"))
        if len(labels) < 2:
            continue
        case_id = "ambient_%s" % row.get("id")
        premise = str(row.get("premise") or "").strip()
        hypothesis = str(row.get("hypothesis") or "").strip()
        if not premise or not hypothesis:
            raise AdapterError("AmbiEnt case %s is incomplete." % case_id)
        cases.append(
            {
                "id": case_id,
                "dataset": "AmbiEnt",
                "source_split": "test",
                "label_scope": "linguist_validated_ambiguous_nli_pair",
                "query": "",
                "claim": hypothesis,
                "contexts": [{"id": "%s_premise" % case_id, "text": premise}],
                "expected_verdict": "unverifiable",
                "upstream_label": ", ".join(labels),
                "upstream_plausible_labels": labels,
                "premise_ambiguous": bool(row.get("premise_ambiguous")),
                "hypothesis_ambiguous": bool(row.get("hypothesis_ambiguous")),
                "upstream_evidence_context_ids": [],
            }
        )
    return cases


def _balanced_sample(
    rows: list[dict[str, Any]], *, per_label: int, seed: int
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["expected_verdict"])].append(row)
    selected = []
    for label in LABELS:
        ordered = sorted(
            groups[label],
            key=lambda row: hashlib.sha256(
                ("%s:%s:%s" % (seed, label, row["id"])).encode("utf-8")
            ).hexdigest(),
        )
        unique_claims = []
        seen_claims = set()
        for row in ordered:
            claim_hash = hashlib.sha256(str(row["claim"]).strip().casefold().encode("utf-8")).hexdigest()
            if claim_hash in seen_claims:
                continue
            seen_claims.add(claim_hash)
            unique_claims.append(row)
        ordered = unique_claims
        if len(ordered) < per_label:
            raise AdapterError("Only %d compatible %s cases are available." % (len(ordered), label))
        selected.extend(ordered[:per_label])
    return sorted(selected, key=lambda row: str(row["id"]))


def _contexts(values: Iterable[tuple[str, object]]) -> list[dict[str, str]]:
    output = []
    for context_id, value in values:
        text = str(value or "").strip()
        if text:
            output.append({"id": context_id, "text": text})
    return output


def _ambient_labels(value: object) -> list[str]:
    allowed = {"entailment", "neutral", "contradiction"}
    labels = []
    for item in str(value or "").split(","):
        label = item.strip().casefold()
        if label and label not in labels:
            if label not in allowed:
                raise AdapterError("Unknown AmbiEnt label %r." % label)
            labels.append(label)
    return labels


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise AdapterError("%s:%d is not an object." % (path, line_number))
        rows.append(value)
    return rows


def _require_source_hash(path: Path, name: str) -> None:
    expected = str(SOURCES[name]["sha256"])
    actual = sha256(path)
    if actual != expected:
        raise AdapterError("%s has sha256 %s; expected %s." % (path, actual, expected))


def _source_record(path: Path, name: str) -> dict[str, Any]:
    return {
        "file": name,
        "url": SOURCES[name]["url"],
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def _zip_member_sha256(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return hashlib.sha256(archive.read(member)).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wice", required=True)
    parser.add_argument("--vitaminc", required=True)
    parser.add_argument("--ambient", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-label", type=int, default=PER_LABEL)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    payload = build_case_pack(
        wice_path=args.wice,
        vitaminc_path=args.vitaminc,
        ambient_path=args.ambient,
        per_label=args.per_label,
        seed=args.seed,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(payload["cases"]), "label_counts": payload["label_counts"]}, indent=2))
    print("wrote %s" % output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
