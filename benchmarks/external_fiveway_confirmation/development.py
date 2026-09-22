"""Build the development-only pack for ambiguity and support-gate calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from benchmarks.jev_v2_verification.run import shared_input


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
SEED = 20260922
PER_LABEL = 25
SOURCE_SPECS = {
    "wice": {
        "sha256": "67531ca79bde4c81d3752fb69d9cb0d3d6763de5c3028f548b83ef053a6f8042",
        "url": (
            "https://raw.githubusercontent.com/ryokamoi/wice/"
            "ddeb6c183665e2a20c5f03c5aa07f03888b9870f/"
            "data/entailment_retrieval/claim/dev.jsonl"
        ),
    },
    "ambient": {
        "sha256": "741e83507c4f9f2d3e8ea3884f5f6f457d478ec3d3d055881d9ec784104d7c0d",
        "url": (
            "https://raw.githubusercontent.com/alisawuffles/ambient/"
            "1fcb43effda068f3047d46b6f9ff0e50e0ee1c1b/AmbiEnt/dev.jsonl"
        ),
    },
    "vitaminc": {
        "sha256": "49d82dc1690cbee420d18e2c26f687a7937710bb211845d2571430dfd4dc0337",
        "url": "https://github.com/TalSchuster/talschuster.github.io/raw/master/static/vitaminc.zip",
        "member": "vitaminc/dev.jsonl",
        "member_sha256": "a3258bc959754c84bade150d3bf447fd9c91a529d93bb676f034fdafda5f26e5",
    },
}


class DevelopmentPackError(ValueError):
    """Raised when the development pack cannot be built exactly."""


def build_development_pack(
    *,
    wice_path: str | Path,
    vitaminc_path: str | Path,
    ambient_path: str | Path,
    per_label: int = PER_LABEL,
    seed: int = SEED,
) -> dict[str, Any]:
    if per_label < 2:
        raise DevelopmentPackError("per_label must be at least 2 for calibration and validation.")
    paths = {
        "wice": Path(wice_path),
        "vitaminc": Path(vitaminc_path),
        "ambient": Path(ambient_path),
    }
    for name, path in paths.items():
        _require_hash(path, str(SOURCE_SPECS[name]["sha256"]))
    candidates = [
        *_wice_cases(paths["wice"]),
        *_vitaminc_cases(paths["vitaminc"]),
        *_ambient_cases(paths["ambient"]),
    ]
    selectable = [case for case in candidates if shared_input(case)[0]]
    selected = _balanced_sample(selectable, per_label=per_label, seed=seed)
    calibration_per_label = max(1, min(per_label - 1, round(per_label * 0.6)))
    selected = _assign_partitions(
        selected, seed=seed, calibration_per_label=calibration_per_label
    )
    counts = Counter(str(case["expected_verdict"]) for case in selected)
    expected_counts = Counter({label: per_label for label in LABELS})
    if counts != expected_counts:
        raise DevelopmentPackError("Development pack is not balanced: %r" % counts)
    return {
        "schema_version": "external-fiveway-development-1.0",
        "dataset": "WiCE+VitaminC+AmbiEnt",
        "split": "development",
        "label_scope": "public_source_labels_aligned_to_contexttrace_claim_verdicts",
        "predictions_used_for_selection": False,
        "selection": {
            "method": "stable_sha256_stratified_unique_claims",
            "seed": seed,
            "per_label": per_label,
            "requires_nonempty_label_blind_selected_evidence": True,
            "candidates_before_evidence_filter": len(candidates),
            "candidates_after_evidence_filter": len(selectable),
            "partition": {
                "method": "stable_sha256_within_label",
                "calibration_per_label": calibration_per_label,
                "validation_per_label": per_label - calibration_per_label,
            },
        },
        "sources": {
            name: {
                "url": SOURCE_SPECS[name]["url"],
                "sha256": _sha256(path),
                **(
                    {
                        "archive_member": SOURCE_SPECS[name]["member"],
                        "archive_member_sha256": _zip_member_sha256(
                            path, str(SOURCE_SPECS[name]["member"])
                        ),
                    }
                    if "member" in SOURCE_SPECS[name]
                    else {}
                ),
            }
            for name, path in paths.items()
        },
        "label_counts": dict(sorted(counts.items())),
        "development_only": True,
        "heldout_confirmation_cases_excluded": True,
        "cases": selected,
    }


def _wice_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for index, row in enumerate(_read_jsonl_bytes(path.read_bytes())):
        upstream = str(row.get("label"))
        source_id = str((row.get("meta") or {}).get("id") or "row%05d" % index)
        case_id = "wice_%s" % source_id
        evidence = row.get("evidence") or []
        contexts = _contexts(
            ("%s_e%04d" % (case_id, evidence_index), text)
            for evidence_index, text in enumerate(evidence)
        )
        if upstream not in WICE_LABELS or not contexts:
            raise DevelopmentPackError("Invalid WiCE development case %s." % case_id)
        cases.append(
            {
                "id": case_id,
                "dataset": "WiCE",
                "source_split": "dev",
                "label_scope": "natural_wikipedia_claim",
                "query": "",
                "claim": str(row.get("claim") or "").strip(),
                "contexts": contexts,
                "expected_verdict": WICE_LABELS[upstream],
                "upstream_label": upstream,
            }
        )
    return cases


def _vitaminc_cases(path: Path) -> list[dict[str, Any]]:
    member = str(SOURCE_SPECS["vitaminc"]["member"])
    with zipfile.ZipFile(path) as archive:
        rows = _read_jsonl_bytes(archive.read(member))
    cases = []
    for row in rows:
        if row.get("label") != "REFUTES" or row.get("revision_type") != "real":
            continue
        source_id = str(row.get("unique_id") or "").strip()
        claim = str(row.get("claim") or "").strip()
        evidence = str(row.get("evidence") or "").strip()
        if not source_id or not claim or not evidence:
            raise DevelopmentPackError("Incomplete VitaminC development row.")
        case_id = "vitaminc_%s" % source_id
        cases.append(
            {
                "id": case_id,
                "dataset": "VitaminC",
                "source_split": "dev",
                "label_scope": "real_wikipedia_revision_claim_evidence_pair",
                "query": "",
                "claim": claim,
                "contexts": [{"id": "%s_evidence" % case_id, "text": evidence}],
                "expected_verdict": "contradicted",
                "upstream_label": "REFUTES",
                "upstream_revision_type": "real",
            }
        )
    return cases


def _ambient_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for row in _read_jsonl_bytes(path.read_bytes()):
        labels = []
        for raw in str(row.get("labels") or "").split(","):
            label = raw.strip().casefold()
            if label and label not in labels:
                labels.append(label)
        if len(labels) < 2:
            continue
        case_id = "ambient_%s" % row.get("id")
        premise = str(row.get("premise") or "").strip()
        claim = str(row.get("hypothesis") or "").strip()
        if not premise or not claim:
            raise DevelopmentPackError("Incomplete AmbiEnt development case %s." % case_id)
        cases.append(
            {
                "id": case_id,
                "dataset": "AmbiEnt",
                "source_split": "dev",
                "label_scope": "linguist_validated_ambiguous_nli_pair",
                "query": "",
                "claim": claim,
                "contexts": [{"id": "%s_premise" % case_id, "text": premise}],
                "expected_verdict": "unverifiable",
                "upstream_label": ", ".join(labels),
                "upstream_plausible_labels": labels,
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
        unique = []
        seen_claims = set()
        for row in ordered:
            key = " ".join(str(row["claim"]).casefold().split())
            if key in seen_claims:
                continue
            seen_claims.add(key)
            unique.append(row)
        if len(unique) < per_label:
            raise DevelopmentPackError("Only %d unique %s cases available." % (len(unique), label))
        selected.extend(unique[:per_label])
    return sorted(selected, key=lambda row: str(row["id"]))


def _assign_partitions(
    rows: list[dict[str, Any]], *, seed: int, calibration_per_label: int
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["expected_verdict"])].append(row)
    output = []
    for label, values in groups.items():
        ordered = sorted(
            values,
            key=lambda row: hashlib.sha256(
                ("partition:%s:%s:%s" % (seed, label, row["id"])).encode("utf-8")
            ).hexdigest(),
        )
        if not 0 < calibration_per_label < len(ordered):
            raise DevelopmentPackError("Invalid calibration partition size.")
        for index, row in enumerate(ordered):
            output.append(
                {
                    **row,
                    "development_partition": (
                        "calibration" if index < calibration_per_label else "validation"
                    ),
                }
            )
    return sorted(output, key=lambda row: str(row["id"]))


def _contexts(values: Iterable[tuple[str, object]]) -> list[dict[str, str]]:
    output = []
    for context_id, value in values:
        text = str(value or "").strip()
        if text:
            output.append({"id": context_id, "text": text})
    return output


def _read_jsonl_bytes(value: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_hash(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise DevelopmentPackError("%s has sha256 %s; expected %s." % (path, actual, expected))


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
    payload = build_development_pack(
        wice_path=args.wice,
        vitaminc_path=args.vitaminc,
        ambient_path=args.ambient,
        per_label=args.per_label,
        seed=args.seed,
    )
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(payload["cases"]), "labels": payload["label_counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
