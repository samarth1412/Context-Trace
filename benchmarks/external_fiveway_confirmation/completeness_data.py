"""Build disjoint WiCE packs for complete-versus-partial support research."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.acquire import SOURCES
from benchmarks.external_fiveway_confirmation.adapter import _wice_cases as test_wice_cases
from benchmarks.external_fiveway_confirmation.development import SOURCE_SPECS
from benchmarks.jev_v2_verification.run import shared_input


LABELS = ("supported", "partially_supported")
DEVELOPMENT_SEED = 20260923
CONFIRMATION_SEED = 20260924


class CompletenessDataError(ValueError):
    """Raised when a completeness pack cannot satisfy its frozen contract."""


def build_pack(
    *,
    source_path: str | Path,
    source_split: str,
    excluded_case_packs: list[str | Path],
    per_label: int,
    seed: int,
    calibration_per_label: int | None = None,
    fixed_development_partition: str | None = None,
) -> dict[str, Any]:
    path = Path(source_path)
    if source_split == "dev":
        expected_hash = str(SOURCE_SPECS["wice"]["sha256"])
        source_url = str(SOURCE_SPECS["wice"]["url"])
        candidates = test_wice_cases(path)
        for candidate in candidates:
            candidate["source_split"] = "dev"
    elif source_split == "test":
        expected_hash = str(SOURCES["wice_test.jsonl"]["sha256"])
        source_url = str(SOURCES["wice_test.jsonl"]["url"])
        candidates = test_wice_cases(path)
    else:
        raise CompletenessDataError("source_split must be dev or test.")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise CompletenessDataError(
            "%s has sha256 %s; expected %s." % (path, actual_hash, expected_hash)
        )
    excluded_ids, excluded_claims = _exclusions(excluded_case_packs)
    eligible = [
        row
        for row in candidates
        if row["expected_verdict"] in LABELS
        and row["id"] not in excluded_ids
        and _normalize(row["claim"]) not in excluded_claims
        and shared_input(row)[0]
    ]
    selected = _balanced_sample(eligible, per_label=per_label, seed=seed)
    split = "development" if source_split == "dev" else "heldout"
    if split == "development":
        if fixed_development_partition:
            if calibration_per_label is not None:
                raise CompletenessDataError(
                    "A fixed partition cannot be combined with calibration_per_label."
                )
            selected = [
                {**row, "development_partition": fixed_development_partition}
                for row in selected
            ]
        else:
            if calibration_per_label is None or not 0 < calibration_per_label < per_label:
                raise CompletenessDataError(
                    "Development pack needs a nontrivial calibration split."
                )
            selected = _assign_partitions(
                selected,
                seed=seed,
                calibration_per_label=calibration_per_label,
            )
    elif calibration_per_label is not None or fixed_development_partition is not None:
        raise CompletenessDataError("Held-out pack cannot define a calibration partition.")
    counts = Counter(str(row["expected_verdict"]) for row in selected)
    if counts != Counter({label: per_label for label in LABELS}):
        raise CompletenessDataError("Pack is not balanced: %r" % counts)
    return {
        "schema_version": "completeness-support-pack-1.0",
        "dataset": "WiCE",
        "split": split,
        "source_split": source_split,
        "task": "complete_support_vs_partial_support",
        "predictions_used_for_selection": False,
        "heldout_used_for_policy_selection": False,
        "selection": {
            "method": "stable_sha256_stratified_disjoint_without_replacement",
            "seed": seed,
            "per_label": per_label,
            "calibration_per_label": calibration_per_label,
            "fixed_development_partition": fixed_development_partition,
            "requires_nonempty_label_blind_selected_evidence": True,
            "excluded_case_packs": [str(Path(value)) for value in excluded_case_packs],
            "eligible_label_counts": dict(
                sorted(Counter(str(row["expected_verdict"]) for row in eligible).items())
            ),
        },
        "source": {
            "url": source_url,
            "sha256": actual_hash,
            "bytes": path.stat().st_size,
        },
        "label_counts": dict(sorted(counts.items())),
        "evidence_regime": {
            "selection": "ContextTrace label-blind shared local selector",
            "max_selected_spans": 8,
            "oracle_evidence_used_as_model_input": False,
        },
        "cases": selected,
    }


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
            raise CompletenessDataError(
                "Only %d eligible %s cases remain; requested %d."
                % (len(unique), label, per_label)
            )
        selected.extend(unique[:per_label])
    return sorted(selected, key=lambda row: str(row["id"]))


def _assign_partitions(
    rows: list[dict[str, Any]], *, seed: int, calibration_per_label: int
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["expected_verdict"])].append(row)
    output = []
    for label in LABELS:
        ordered = sorted(
            groups[label],
            key=lambda row: hashlib.sha256(
                ("partition:%s:%s:%s" % (seed, label, row["id"])).encode("utf-8")
            ).hexdigest(),
        )
        for index, row in enumerate(ordered):
            copied = dict(row)
            copied["development_partition"] = (
                "calibration" if index < calibration_per_label else "validation"
            )
            output.append(copied)
    return sorted(output, key=lambda row: str(row["id"]))


def _exclusions(paths: list[str | Path]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    claims: set[str] = set()
    for value in paths:
        payload = json.loads(Path(value).read_text(encoding="utf-8"))
        for row in payload.get("cases") or []:
            ids.add(str(row["id"]))
            claims.add(_normalize(row["claim"]))
    return ids, claims


def _normalize(value: object) -> str:
    return " ".join(str(value).casefold().split())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-split", choices=("dev", "test"), required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--per-label", type=int, required=True)
    parser.add_argument("--calibration-per-label", type=int)
    parser.add_argument("--fixed-development-partition")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    default_seed = DEVELOPMENT_SEED if args.source_split == "dev" else CONFIRMATION_SEED
    payload = build_pack(
        source_path=args.source,
        source_split=args.source_split,
        excluded_case_packs=args.exclude,
        per_label=args.per_label,
        calibration_per_label=args.calibration_per_label,
        fixed_development_partition=args.fixed_development_partition,
        seed=args.seed if args.seed is not None else default_seed,
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
