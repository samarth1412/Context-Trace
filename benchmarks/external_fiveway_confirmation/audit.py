"""Audit label alignment, input isolation, retrieval, and prior-pack overlap."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import LABELS
from benchmarks.jev_v2_verification.run import shared_input


class AuditError(RuntimeError):
    """Raised when the frozen confirmation set violates its protocol."""


def audit_case_pack(
    cases_path: str | Path,
    *,
    prior_case_packs: list[str | Path] | None = None,
) -> dict[str, Any]:
    path = Path(cases_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise AuditError("Case pack is empty.")
    counts = Counter(str(case.get("expected_verdict")) for case in cases)
    if set(counts) != set(LABELS) or len(set(counts.values())) != 1:
        raise AuditError("Expected a balanced pack containing exactly all five verdicts.")

    prior_claim_hashes: set[str] = set()
    prior_input_hashes: set[str] = set()
    prior_ids: set[str] = set()
    loaded_prior_paths = []
    for prior_path in prior_case_packs or []:
        source = Path(prior_path)
        if not source.exists():
            continue
        prior_payload = json.loads(source.read_text(encoding="utf-8"))
        prior_rows = prior_payload.get("cases")
        if not isinstance(prior_rows, list):
            continue
        loaded_prior_paths.append(str(source))
        for row in prior_rows:
            prior_ids.add(str(row.get("id") or ""))
            prior_claim_hashes.add(_text_hash(str(row.get("claim") or row.get("answer") or "")))
            prior_input_hashes.add(_case_input_hash(row))

    ids = set()
    claim_hashes = set()
    duplicate_claims = []
    overlaps = {"case_ids": [], "normalized_claims": [], "normalized_inputs": []}
    selected_counts = Counter()
    selected_characters = []
    retrieval: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case in cases:
        case_id = str(case.get("id") or "")
        if not case_id or case_id in ids:
            raise AuditError("Case ids must be non-empty and unique: %r." % case_id)
        ids.add(case_id)
        if "predictions" in case:
            raise AuditError("Frozen case %s contains predictions." % case_id)
        _validate_mapping(case)
        claim_hash = _text_hash(str(case.get("claim") or ""))
        if claim_hash in claim_hashes:
            duplicate_claims.append(case_id)
        claim_hashes.add(claim_hash)
        if case_id in prior_ids:
            overlaps["case_ids"].append(case_id)
        if claim_hash in prior_claim_hashes:
            overlaps["normalized_claims"].append(case_id)
        if _case_input_hash(case) in prior_input_hashes:
            overlaps["normalized_inputs"].append(case_id)

        selected, input_audit = shared_input(case)
        if not selected or len(selected) > 8:
            raise AuditError("Case %s selected %d evidence spans." % (case_id, len(selected)))
        if input_audit["evaluation_label_sent"] is not False:
            raise AuditError("Case %s did not attest label isolation." % case_id)
        serialized = json.dumps(input_audit["exact_shared_input"], sort_keys=True)
        for forbidden in ("expected_verdict", "upstream_label", "upstream_evidence_context_ids"):
            if forbidden in serialized:
                raise AuditError("Case %s leaked %s into model input." % (case_id, forbidden))
        selected_counts[len(selected)] += 1
        selected_characters.append(sum(len(context.text) for context in selected))
        annotated = set(case.get("upstream_evidence_context_ids") or [])
        if annotated:
            chosen = {context.id.rsplit(":", 2)[0] for context in selected}
            values = retrieval[str(case["expected_verdict"])]
            values[0] += bool(annotated & chosen)
            values[1] += 1

    if any(overlaps.values()):
        raise AuditError("Confirmation cases overlap prior packs: %r" % overlaps)
    return {
        "valid": True,
        "case_pack": str(path),
        "case_pack_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cases": len(cases),
        "label_counts": dict(sorted(counts.items())),
        "duplicate_normalized_claims_within_pack": duplicate_claims,
        "prior_case_packs_checked": loaded_prior_paths,
        "prior_overlap": overlaps,
        "label_isolation": {
            "evaluation_labels_sent": False,
            "sent_fields": ["query", "claim", "selected_evidence"],
        },
        "selection": {
            "nonempty_for_every_case": True,
            "max_spans": 8,
            "selected_span_count_distribution": {
                str(key): value for key, value in sorted(selected_counts.items())
            },
            "selected_characters": {
                "minimum": min(selected_characters),
                "mean": round(sum(selected_characters) / len(selected_characters), 2),
                "maximum": max(selected_characters),
            },
            "at_least_one_upstream_annotated_span_retrieved": {
                label: {
                    "hits": values[0],
                    "annotated_cases": values[1],
                    "rate": round(values[0] / values[1], 4),
                }
                for label, values in sorted(retrieval.items())
            },
        },
    }


def _validate_mapping(case: dict[str, Any]) -> None:
    dataset = str(case.get("dataset"))
    upstream = str(case.get("upstream_label"))
    expected = str(case.get("expected_verdict"))
    valid = bool(
        (dataset == "WiCE" and WICE_MAPPING.get(upstream) == expected)
        or (
            dataset == "VitaminC"
            and upstream == "REFUTES"
            and case.get("upstream_revision_type") == "real"
            and expected == "contradicted"
        )
        or (
            dataset == "AmbiEnt"
            and expected == "unverifiable"
            and len(case.get("upstream_plausible_labels") or []) >= 2
        )
    )
    if not valid:
        raise AuditError("Case %s has an invalid source-label mapping." % case.get("id"))


WICE_MAPPING = {
    "supported": "supported",
    "partially_supported": "partially_supported",
    "not_supported": "unsupported",
}


def _case_input_hash(case: dict[str, Any]) -> str:
    contexts = case.get("contexts") or []
    value = {
        "claim": _normalize(str(case.get("claim") or case.get("answer") or "")),
        "contexts": sorted(
            _normalize(str(context.get("text") or ""))
            for context in contexts
            if isinstance(context, dict)
        ),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(_normalize(value).encode("utf-8")).hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--prior-case-pack", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = audit_case_pack(args.cases, prior_case_packs=args.prior_case_pack)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
