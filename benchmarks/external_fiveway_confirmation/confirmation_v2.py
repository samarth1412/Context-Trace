"""Build a second confirmation pack disjoint from prior ContextTrace experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import (
    LABELS,
    VITAMINC_MEMBER,
    _ambient_cases,
    _require_source_hash,
    _source_record,
    _vitaminc_cases,
    _wice_cases,
    _zip_member_sha256,
)
from benchmarks.jev_v2_verification.run import shared_input


SEED = 20260922
PER_LABEL = 7


class ConfirmationV2Error(ValueError):
    """Raised when the disjoint confirmation pack cannot be built exactly."""


def build_disjoint_pack(
    *,
    wice_path: str | Path,
    vitaminc_path: str | Path,
    ambient_path: str | Path,
    excluded_case_packs: list[str | Path],
    per_label: int = PER_LABEL,
    seed: int = SEED,
) -> dict[str, Any]:
    paths = {
        "wice": Path(wice_path),
        "vitaminc": Path(vitaminc_path),
        "ambient": Path(ambient_path),
    }
    _require_source_hash(paths["wice"], "wice_test.jsonl")
    _require_source_hash(paths["vitaminc"], "vitaminc.zip")
    _require_source_hash(paths["ambient"], "ambient_test.jsonl")
    excluded_ids, excluded_claims = _exclusions(excluded_case_packs)
    candidates = [
        *_wice_cases(paths["wice"]),
        *_vitaminc_cases(paths["vitaminc"]),
        *_ambient_cases(paths["ambient"]),
    ]
    disjoint = [
        row
        for row in candidates
        if row["id"] not in excluded_ids and _normalize(row["claim"]) not in excluded_claims
    ]
    eligible = [row for row in disjoint if shared_input(row)[0]]
    selected = _balanced_sample(eligible, per_label=per_label, seed=seed)
    counts = Counter(str(row["expected_verdict"]) for row in selected)
    if counts != Counter({label: per_label for label in LABELS}):
        raise ConfirmationV2Error("Second confirmation pack is not balanced: %r" % counts)
    return {
        "schema_version": "external-fiveway-confirmation-2.0",
        "dataset": "WiCE+VitaminC+AmbiEnt",
        "split": "heldout",
        "label_scope": "public_human_labels_aligned_to_contexttrace_claim_verdicts",
        "independent_source_labels": True,
        "predictions_used_for_selection": False,
        "selection": {
            "method": "stable_sha256_stratified_disjoint_without_replacement",
            "seed": seed,
            "per_label": per_label,
            "excluded_case_packs": [str(Path(path)) for path in excluded_case_packs],
            "excluded_case_count": len(excluded_ids),
            "excluded_normalized_claim_count": len(excluded_claims),
            "disjoint_candidates_before_evidence_filter": len(disjoint),
            "disjoint_candidates_after_evidence_filter": len(eligible),
            "requires_nonempty_label_blind_selected_evidence": True,
            "limiting_slice": "WiCE.not_supported",
            "eligible_label_counts": dict(
                sorted(Counter(str(row["expected_verdict"]) for row in eligible).items())
            ),
        },
        "label_mapping": {
            "WiCE.supported": "supported",
            "WiCE.partially_supported": "partially_supported",
            "WiCE.not_supported": "unsupported",
            "VitaminC.real.REFUTES": "contradicted",
            "AmbiEnt.multiple_plausible_NLI_labels": "unverifiable",
        },
        "evidence_regime": {
            "source": "complete upstream evidence segmented into source-provided spans",
            "selection": "ContextTrace label-blind shared local selector at evaluation time",
            "max_selected_spans": 8,
            "oracle_evidence_used_as_model_input": False,
        },
        "sources": {
            "wice": _source_record(paths["wice"], "wice_test.jsonl"),
            "vitaminc": {
                **_source_record(paths["vitaminc"], "vitaminc.zip"),
                "archive_member": VITAMINC_MEMBER,
                "archive_member_sha256": _zip_member_sha256(
                    paths["vitaminc"], VITAMINC_MEMBER
                ),
            },
            "ambient": _source_record(paths["ambient"], "ambient_test.jsonl"),
        },
        "label_counts": dict(sorted(counts.items())),
        "limitations": [
            "The second check has seven cases per label because only seven unused WiCE test unsupported claims remain.",
            "Public-test pretraining contamination cannot be ruled out.",
            "Upstream labels are conservatively aligned rather than newly annotated for ContextTrace.",
        ],
        "cases": selected,
    }


def _exclusions(paths: list[str | Path]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    claims: set[str] = set()
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for row in payload.get("cases") or []:
            ids.add(str(row["id"]))
            claims.add(_normalize(row["claim"]))
    return ids, claims


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
        unique = []
        seen = set()
        for row in ordered:
            normalized = _normalize(row["claim"])
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(row)
        if len(unique) < per_label:
            raise ConfirmationV2Error(
                "Only %d disjoint %s cases remain; requested %d."
                % (len(unique), label, per_label)
            )
        selected.extend(unique[:per_label])
    return sorted(selected, key=lambda row: str(row["id"]))


def _normalize(value: object) -> str:
    return " ".join(str(value).casefold().split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wice", required=True)
    parser.add_argument("--vitaminc", required=True)
    parser.add_argument("--ambient", required=True)
    parser.add_argument("--exclude", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-label", type=int, default=PER_LABEL)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    payload = build_disjoint_pack(
        wice_path=args.wice,
        vitaminc_path=args.vitaminc,
        ambient_path=args.ambient,
        excluded_case_packs=args.exclude,
        per_label=args.per_label,
        seed=args.seed,
    )
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"cases": len(payload["cases"]), "label_counts": payload["label_counts"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
