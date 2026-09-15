from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any


TRACE_SCHEMA_VERSION = "1.0"
CLAIM_VERIFICATION_SCHEMA_VERSION = "1.0"
DIAGNOSIS_SCHEMA_VERSION = "1.0"
REPAIR_PLAN_SCHEMA_VERSION = "1.0"
REGRESSION_CASE_SCHEMA_VERSION = "1.0"

TAXONOMY_VERSION = "1.0"
VERIFIER_VERSION = "semantic_v1_calibrated"
DEFAULT_PROFILE_ID = "full_v1"

SCHEMA_FILES = {
    "TraceV1": "trace-v1.schema.json",
    "ClaimVerificationV1": "claim-verification-v1.schema.json",
    "ClaimVerificationHybridV2": "claim-verification-hybrid-v2.schema.json",
    "DiagnosisV1": "diagnosis-v1.schema.json",
    "RepairPlanV1": "repair-plan-v1.schema.json",
    "RegressionCaseV1": "regression-case-v1.schema.json",
}


def artifact_provenance(*, schema_version: str, profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, str]:
    """Return the required provenance fields for a public artifact."""

    return {
        "schema_version": schema_version,
        "taxonomy_version": TAXONOMY_VERSION,
        "verifier_version": VERIFIER_VERSION,
        "profile_id": profile_id,
    }


def verification_profile_id(profile: dict[str, Any]) -> str:
    """Return a stable ID for custom verification profiles."""

    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"))
    default = {
        "abstention_logic": True,
        "citation_alignment": True,
        "contradiction_checks": True,
        "evidence_span_localization": True,
        "root_cause_inference": True,
        "semantic_normalization": True,
        "source_assessment": True,
    }
    if profile == default:
        return DEFAULT_PROFILE_ID
    return "custom_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def load_json_schema(name: str) -> dict[str, Any]:
    """Load one of the packaged public JSON Schemas by contract name."""

    filename = SCHEMA_FILES.get(name)
    if filename is None:
        raise KeyError("Unknown ContextTrace schema: %s" % name)
    resource = resources.files("contexttrace.schemas").joinpath(filename)
    return json.loads(resource.read_text(encoding="utf-8"))


def build_regression_case(
    *,
    case_id: str,
    trace: dict[str, Any],
    expected: dict[str, Any],
    profile_id: str = DEFAULT_PROFILE_ID,
) -> dict[str, Any]:
    """Build a portable, versioned regression case artifact."""

    return {
        **artifact_provenance(
            schema_version=REGRESSION_CASE_SCHEMA_VERSION,
            profile_id=profile_id,
        ),
        "case_id": str(case_id),
        "trace": dict(trace),
        "expected": dict(expected),
    }
