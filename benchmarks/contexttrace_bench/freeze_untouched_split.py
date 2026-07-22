from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_SEPARATION_FIELDS = (
    "track",
    "source_family",
    "source_document_id",
    "domain",
    "publication_window",
)
DISJOINT_FIELDS = (
    "source_family",
    "source_document_id",
    "domain",
    "publication_window",
)


def freeze_split(case_pack: dict[str, Any], calibration: dict[str, Any]) -> dict[str, Any]:
    cases = case_pack.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Candidate test pack must contain a non-empty cases list.")

    calibration_cases = calibration.get("cases") or []
    if not isinstance(calibration_cases, list):
        raise ValueError("Calibration pack cases must be a list.")

    seen_ids: set[str] = set()
    normalized: list[dict[str, str]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError("cases[%s] must be an object." % index)
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in seen_ids:
            raise ValueError("Every candidate test case must have a unique non-empty id.")
        seen_ids.add(case_id)
        record = {"id": case_id}
        for field in REQUIRED_SEPARATION_FIELDS:
            value = str(case.get(field) or (case.get("metadata") or {}).get(field) or "").strip()
            if not value:
                raise ValueError("Case %s is missing required separation field %s." % (case_id, field))
            record[field] = value
        normalized.append(record)

    calibration_values = {
        field: {
            str(case.get(field) or (case.get("metadata") or {}).get(field) or "").strip()
            for case in calibration_cases
            if isinstance(case, dict)
        }
        for field in DISJOINT_FIELDS
    }
    overlaps: dict[str, list[str]] = {}
    for field in DISJOINT_FIELDS:
        values = sorted({record[field] for record in normalized} & calibration_values[field])
        if values:
            overlaps[field] = values
    if overlaps:
        raise ValueError("Candidate split overlaps calibration data: %s" % json.dumps(overlaps, sort_keys=True))

    normalized.sort(key=lambda item: item["id"])
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 1,
        "status": "frozen_unscored",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(normalized),
        "separation_fields": list(REQUIRED_SEPARATION_FIELDS),
        "cases": normalized,
        "manifest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "policy": "Publish this manifest before successor-verifier implementation; score once after lock.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze and hash a source-family/domain/publication-window-disjoint test split."
    )
    parser.add_argument("--case-pack", required=True)
    parser.add_argument("--calibration-pack", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    candidate = json.loads(Path(args.case_pack).read_text(encoding="utf-8"))
    calibration = json.loads(Path(args.calibration_pack).read_text(encoding="utf-8"))
    manifest = freeze_split(candidate, calibration)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Frozen %s cases: %s" % (manifest["case_count"], manifest["manifest_sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
