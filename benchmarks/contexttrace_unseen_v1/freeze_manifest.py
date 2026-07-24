from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from jsonschema import (  # type: ignore[import-untyped]
        Draft202012Validator,
        FormatChecker,
    )
except ImportError as exc:  # pragma: no cover - dependency failure is fail-closed
    raise RuntimeError(
        "freeze_manifest requires jsonschema; install the ContextTrace test dependencies."
    ) from exc


SCHEMA_DIRECTORY = Path(__file__).resolve().parent
SOURCE_SCHEMA_PATH = SCHEMA_DIRECTORY / "source_manifest.schema.json"
CASE_SCHEMA_PATH = SCHEMA_DIRECTORY / "case_manifest.schema.json"

FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "adjudication",
        "adjudicated_label",
        "annotation",
        "annotations",
        "claim_verdict",
        "evidence_span",
        "failure_label",
        "gold",
        "gold_label",
        "gold_labels",
        "prediction",
        "predictions",
        "reviewer_note",
        "root_cause",
        "system_prediction",
        "verdict",
    }
)
FORBIDDEN_VERIFIERS = frozenset(
    {
        "semantic_v1_calibrated",
        "semantic_core_v2",
    }
)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
DOMAIN_GROUPS = frozenset(
    {
        "software_product_documentation",
        "policy_regulatory",
        "support_operational",
    }
)
RETRIEVAL_FAMILIES = frozenset({"bm25", "vector", "hybrid"})
REDISTRIBUTION_ORDER = {
    "permitted": 0,
    "metadata_only": 1,
    "prohibited": 2,
}


class FreezeError(ValueError):
    """Raised when a candidate manifest cannot be frozen safely."""


@dataclass(frozen=True)
class CompositionPolicy:
    minimum_natural_cases: int = 300
    maximum_natural_cases: int = 500
    minimum_source_families: int = 36
    minimum_families_per_domain: int = 12
    maximum_family_fraction: float = 0.10
    temporal_target_minimum: int = 80
    temporal_target_maximum: int = 120

    @classmethod
    def small_fixture(cls) -> CompositionPolicy:
        """Return a policy for structural tests, never for a final freeze."""

        return cls(
            minimum_natural_cases=1,
            maximum_natural_cases=100,
            minimum_source_families=1,
            minimum_families_per_domain=0,
            maximum_family_fraction=1.0,
            temporal_target_minimum=0,
            temporal_target_maximum=100,
        )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FreezeError(f"Normalized text artifact is not UTF-8: {path}") from exc
    normalized = unicodedata.normalize("NFKC", text)
    normalized = " ".join(normalized.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FreezeError(f"Could not read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FreezeError(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise FreezeError(f"{path} must contain a JSON object.")
    return payload


def _schema(path: Path) -> dict[str, Any]:
    return _load_json(path)


def _format_path(parts: Iterable[Any]) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def _validate_schema(
    payload: Mapping[str, Any],
    schema_path: Path,
    *,
    label: str,
) -> None:
    validator = Draft202012Validator(
        _schema(schema_path),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = _format_path(first.absolute_path)
        raise FreezeError(f"{label} schema violation at {location}: {first.message}")


def _parse_timestamp(value: str, *, field: str) -> datetime:
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise FreezeError(
            f"{field} is not a valid ISO-8601 timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FreezeError(f"{field} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def _safe_artifact_path(root: Path, relative_path: str, *, field: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise FreezeError(f"{field} must be a safe relative path: {relative_path}")
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise FreezeError(f"{field} escapes the artifact root: {relative_path}")
    if not resolved.is_file():
        raise FreezeError(f"{field} does not exist or is not a file: {relative_path}")
    return resolved


def _verify_file_hash(
    root: Path,
    relative_path: str,
    expected_sha256: str,
    *,
    field: str,
) -> Path:
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise FreezeError(f"{field} has a missing or invalid SHA-256 value.")
    path = _safe_artifact_path(root, relative_path, field=field)
    actual = file_sha256(path)
    if actual != expected_sha256:
        raise FreezeError(
            f"{field} hash mismatch for {relative_path}: expected "
            f"{expected_sha256}, got {actual}"
        )
    return path


def _walk_forbidden_keys(value: Any, *, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_LABEL_KEYS:
                findings.append(child_path)
            findings.extend(_walk_forbidden_keys(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_walk_forbidden_keys(child, path=f"{path}[{index}]"))
    return findings


def _require_no_label_fields(value: Any, *, label: str) -> None:
    findings = _walk_forbidden_keys(value)
    if findings:
        preview = ", ".join(findings[:5])
        raise FreezeError(f"{label} contains forbidden label-derived fields: {preview}")


def _unique_index(
    records: Sequence[Mapping[str, Any]],
    field: str,
    *,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        value = str(record[field])
        if value in indexed:
            raise FreezeError(f"Duplicate {label} {field}: {value}")
        indexed[value] = record
    return indexed


def _validate_source_artifacts(
    sources: Sequence[Mapping[str, Any]],
    *,
    artifact_root: Path,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for source in sources:
        source_id = str(source["source_id"])
        snapshot_path = str(source["snapshot_path"])
        snapshot_sha = str(source["snapshot_sha256"])
        _verify_file_hash(
            artifact_root,
            snapshot_path,
            snapshot_sha,
            field=f"source {source_id} snapshot_path",
        )
        artifacts[snapshot_path] = snapshot_sha

        normalized_path_value = str(source["normalized_text_path"])
        normalized_path = _safe_artifact_path(
            artifact_root,
            normalized_path_value,
            field=f"source {source_id} normalized_text_path",
        )
        expected_normalized = str(source["normalized_content_sha256"])
        if not SHA256_PATTERN.fullmatch(expected_normalized):
            raise FreezeError(
                f"source {source_id} has a missing or invalid normalized content hash."
            )
        actual_normalized = normalized_text_sha256(normalized_path)
        if actual_normalized != expected_normalized:
            raise FreezeError(
                f"source {source_id} normalized content hash mismatch: expected "
                f"{expected_normalized}, got {actual_normalized}"
            )
        artifacts[normalized_path_value] = file_sha256(normalized_path)
    return artifacts


def _validate_source_policy(
    sources: Sequence[Mapping[str, Any]], *, label: str
) -> None:
    for source in sources:
        source_id = str(source["source_id"])
        license_record = source["license"]
        access = source["access"]
        if license_record["review_status"] != "approved":
            raise FreezeError(
                f"{label} source {source_id} license review is not approved."
            )
        if not access["collection_permitted"]:
            raise FreezeError(f"{label} source {source_id} does not permit collection.")
        if access["access_class"] != "public":
            raise FreezeError(
                f"{label} source {source_id} is restricted; untouched public-corpus "
                "freezing is limited to public sources."
            )
        if source["privacy_classification"] == "authorized_restricted":
            raise FreezeError(f"{label} source {source_id} is privacy-restricted.")


def _validate_source_uniqueness(
    sources: Sequence[Mapping[str, Any]], *, label: str
) -> None:
    _unique_index(sources, "source_id", label=label)
    _unique_index(sources, "source_document_id", label=label)

    by_snapshot: dict[str, Mapping[str, Any]] = {}
    by_normalized: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        source_id = str(source["source_id"])
        for field, index in (
            ("snapshot_sha256", by_snapshot),
            ("normalized_content_sha256", by_normalized),
        ):
            value = str(source[field])
            previous = index.get(value)
            if previous is None:
                index[value] = source
                continue
            compatible = all(
                previous[key] == source[key]
                for key in (
                    "source_family",
                    "domain_id",
                    "near_duplicate_cluster_id",
                )
            )
            if not compatible:
                raise FreezeError(
                    f"{label} source {source_id} duplicates {field} across forbidden "
                    "source-family/domain boundaries."
                )


def _overlap_values(
    candidates: Sequence[Mapping[str, Any]],
    calibration: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
) -> dict[str, list[str]]:
    overlaps: dict[str, list[str]] = {}
    for field in dimensions:
        candidate_values = {str(record[field]) for record in candidates}
        calibration_values = {str(record[field]) for record in calibration}
        shared = sorted(candidate_values & calibration_values)
        if shared:
            overlaps[field] = shared
    return overlaps


def _most_restrictive_redistribution(
    sources: Sequence[Mapping[str, Any]],
) -> str:
    return max(
        (str(source["license"]["redistribution"]) for source in sources),
        key=REDISTRIBUTION_ORDER.__getitem__,
    )


def _validate_trace_artifact(
    case: Mapping[str, Any],
    *,
    artifact_root: Path,
) -> tuple[str, str]:
    case_id = str(case["case_id"])
    relative_path = str(case["trace_artifact_path"])
    expected_sha = str(case["trace_sha256"])
    path = _verify_file_hash(
        artifact_root,
        relative_path,
        expected_sha,
        field=f"case {case_id} trace_artifact_path",
    )
    trace = _load_json(path)
    _require_no_label_fields(trace, label=f"case {case_id} trace artifact")

    if trace.get("case_id") != case_id:
        raise FreezeError(f"case {case_id} trace artifact has a mismatched case_id.")
    query = trace.get("query")
    answer = trace.get("answer")
    if not isinstance(query, str) or not query.strip():
        raise FreezeError(f"case {case_id} trace artifact requires a non-empty query.")
    if not isinstance(answer, str) or not answer.strip():
        raise FreezeError(f"case {case_id} trace artifact requires a non-empty answer.")
    if len(answer) != case["answer_length_chars"]:
        raise FreezeError(
            f"case {case_id} answer_length_chars does not match the trace."
        )

    retrieved = trace.get("retrieved_chunks")
    if not isinstance(retrieved, list):
        raise FreezeError(f"case {case_id} trace artifact requires retrieved_chunks.")
    retrieved_ids: list[str] = []
    for index, chunk in enumerate(retrieved):
        if not isinstance(chunk, dict):
            raise FreezeError(
                f"case {case_id} retrieved_chunks[{index}] must be an object."
            )
        chunk_id = str(chunk.get("id") or "").strip()
        text = chunk.get("text")
        if not chunk_id or not isinstance(text, str):
            raise FreezeError(
                f"case {case_id} retrieved_chunks[{index}] requires id and text."
            )
        retrieved_ids.append(chunk_id)
    if len(retrieved_ids) != len(set(retrieved_ids)):
        raise FreezeError(f"case {case_id} trace artifact has duplicate chunk IDs.")
    if set(retrieved_ids) != set(case["retrieved_chunk_ids"]):
        raise FreezeError(f"case {case_id} retrieved_chunk_ids do not match the trace.")

    selected = trace.get("selected_context_ids")
    if not isinstance(selected, list) or set(selected) != set(
        case["selected_context_ids"]
    ):
        raise FreezeError(
            f"case {case_id} selected_context_ids do not match the trace."
        )
    if not set(selected).issubset(set(retrieved_ids)):
        raise FreezeError(f"case {case_id} selected contexts were not retrieved.")
    if len(selected) != case["context_count"]:
        raise FreezeError(
            f"case {case_id} context_count does not match selected contexts."
        )

    citations = trace.get("citations")
    if not isinstance(citations, list):
        raise FreezeError(f"case {case_id} trace artifact requires a citations list.")
    return relative_path, expected_sha


def _validate_cases(
    case_manifest: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    *,
    artifact_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    cases = case_manifest["cases"]
    if not cases:
        raise FreezeError("Candidate case manifest must contain at least one case.")
    _require_no_label_fields(case_manifest, label="Candidate case manifest")
    indexed_sources = _unique_index(sources, "source_id", label="candidate source")
    _unique_index(cases, "case_id", label="candidate case")
    trace_paths: set[str] = set()
    for case in cases:
        trace_path = str(case["trace_artifact_path"])
        if trace_path in trace_paths:
            raise FreezeError(
                f"Duplicate trace artifact path across cases: {trace_path}"
            )
        trace_paths.add(trace_path)

    created_at = _parse_timestamp(
        str(case_manifest["created_at"]),
        field="case manifest created_at",
    )
    artifacts: dict[str, str] = {}
    document_tracks: dict[str, set[str]] = {}
    normalized_cases: list[dict[str, Any]] = []

    label_access = case_manifest["label_access"]
    if (
        label_access["labels_created"]
        or label_access["labels_accessible"]
        or label_access["first_accessed_at"] is not None
    ):
        raise FreezeError(
            "Labels existed or were accessible before the candidate manifest freeze."
        )

    for case in cases:
        case_id = str(case["case_id"])
        generated_at = _parse_timestamp(
            str(case["collection_timestamp"]),
            field=f"case {case_id} collection_timestamp",
        )
        if generated_at > created_at:
            raise FreezeError(f"case {case_id} was generated after manifest creation.")
        if case["labels_accessible_at_generation"]:
            raise FreezeError(
                f"case {case_id} was generated after labels were accessible."
            )
        if case["verifier_history"]:
            identifiers = {
                str(entry["identifier"]).casefold()
                for entry in case["verifier_history"]
            }
            forbidden = sorted(identifiers & FORBIDDEN_VERIFIERS)
            detail = ", ".join(forbidden or sorted(identifiers))
            raise FreezeError(
                f"case {case_id} was passed through a verifier before freeze: {detail}"
            )

        source_ids = [str(value) for value in case["source_ids"]]
        missing_sources = sorted(set(source_ids) - indexed_sources.keys())
        if missing_sources:
            raise FreezeError(
                f"case {case_id} references unknown sources: {missing_sources}"
            )
        if case["primary_source_id"] not in source_ids:
            raise FreezeError(f"case {case_id} primary_source_id is not in source_ids.")
        selected_sources = [indexed_sources[source_id] for source_id in source_ids]
        primary = indexed_sources[str(case["primary_source_id"])]

        for field in (
            "source_family",
            "source_document_id",
            "domain_group",
            "domain_id",
            "publication_window",
            "source_url",
            "canonical_identifier",
        ):
            if case[field] != primary[field]:
                raise FreezeError(
                    f"case {case_id} {field} does not match its primary source."
                )
        if case["source_snapshot_sha256"] != primary["snapshot_sha256"]:
            raise FreezeError(
                f"case {case_id} source_snapshot_sha256 does not match its primary source."
            )

        for source in selected_sources:
            collected_at = _parse_timestamp(
                str(source["collected_at"]),
                field=f"source {source['source_id']} collected_at",
            )
            if collected_at > generated_at:
                raise FreezeError(
                    f"case {case_id} was generated before source "
                    f"{source['source_id']} was collected."
                )
            document_tracks.setdefault(
                str(source["source_document_id"]),
                set(),
            ).add(str(case["track"]))

        expected_license_ids = sorted(
            {str(source["license"]["license_id"]) for source in selected_sources}
        )
        if sorted(case["license_access"]["license_ids"]) != expected_license_ids:
            raise FreezeError(f"case {case_id} license_ids do not match its sources.")
        expected_redistribution = _most_restrictive_redistribution(selected_sources)
        if case["license_access"]["redistribution"] != expected_redistribution:
            raise FreezeError(
                f"case {case_id} redistribution is less restrictive than its sources."
            )
        if (
            any(
                source["privacy_classification"] == "public_pii_review_required"
                for source in selected_sources
            )
            and case["privacy_classification"] != "public_pii_reviewed"
        ):
            raise FreezeError(f"case {case_id} has not completed required PII review.")

        if case["chunking"]["overlap"] >= case["chunking"]["size"]:
            raise FreezeError(
                f"case {case_id} chunk overlap must be smaller than size."
            )
        reranking = case["reranking"]
        reranking_values = (
            reranking["implementation"],
            reranking["revision"],
            reranking["top_n"],
        )
        if reranking["enabled"] and any(value is None for value in reranking_values):
            raise FreezeError(f"case {case_id} enabled reranking lacks configuration.")
        if not reranking["enabled"] and any(
            value is not None for value in reranking_values
        ):
            raise FreezeError(
                f"case {case_id} disabled reranking must use null configuration."
            )

        pair = case.get("source_condition_pair")
        if case["track"] == "temporal_source_condition":
            if not isinstance(pair, dict):
                raise FreezeError(
                    f"case {case_id} temporal track requires a source pair."
                )
            pair_ids = {pair["left_source_id"], pair["right_source_id"]}
            if len(pair_ids) != 2 or not pair_ids.issubset(set(source_ids)):
                raise FreezeError(
                    f"case {case_id} source-condition pair must name two case sources."
                )
        elif pair is not None:
            raise FreezeError(
                f"case {case_id} Natural OOD case cannot contain a source-condition pair."
            )

        path, expected_sha = _validate_trace_artifact(
            case,
            artifact_root=artifact_root,
        )
        artifacts[path] = expected_sha
        normalized_cases.append(copy.deepcopy(dict(case)))

    crossed = {
        document: sorted(tracks)
        for document, tracks in document_tracks.items()
        if len(tracks) > 1
    }
    if crossed:
        raise FreezeError(
            "Source documents cross forbidden track boundaries: "
            f"{canonical_json(crossed)}"
        )

    normalized_cases.sort(key=lambda item: item["case_id"])
    return normalized_cases, artifacts


def _composition(
    cases: Sequence[Mapping[str, Any]],
    *,
    policy: CompositionPolicy,
) -> dict[str, Any]:
    natural = [case for case in cases if case["track"] == "natural_ood"]
    temporal = [case for case in cases if case["track"] == "temporal_source_condition"]
    natural_count = len(natural)
    if not (
        policy.minimum_natural_cases <= natural_count <= policy.maximum_natural_cases
    ):
        raise FreezeError(
            "Natural OOD composition is outside the frozen range: "
            f"{natural_count} not in "
            f"[{policy.minimum_natural_cases}, {policy.maximum_natural_cases}]."
        )

    groups = {str(case["domain_group"]) for case in natural}
    if policy.minimum_families_per_domain and groups != DOMAIN_GROUPS:
        raise FreezeError(
            "Natural OOD cases must cover all three preregistered domain groups."
        )
    families = {str(case["source_family"]) for case in natural}
    if len(families) < policy.minimum_source_families:
        raise FreezeError(
            f"Natural OOD requires at least {policy.minimum_source_families} "
            f"source families; found {len(families)}."
        )

    family_counts: dict[str, int] = {}
    for case in natural:
        family = str(case["source_family"])
        family_counts[family] = family_counts.get(family, 0) + 1
    if (
        natural
        and max(family_counts.values()) / natural_count > policy.maximum_family_fraction
    ):
        raise FreezeError("A source family exceeds the maximum Natural OOD share.")

    for group in DOMAIN_GROUPS:
        group_families = {
            str(case["source_family"])
            for case in natural
            if case["domain_group"] == group
        }
        if len(group_families) < policy.minimum_families_per_domain:
            raise FreezeError(
                f"Domain group {group} requires at least "
                f"{policy.minimum_families_per_domain} source families."
            )

    retrieval_families = {str(case["retrieval"]["family"]) for case in natural}
    if policy.minimum_families_per_domain and retrieval_families != RETRIEVAL_FAMILIES:
        raise FreezeError(
            "Natural OOD must include BM25, vector, and hybrid retrieval."
        )
    if policy.minimum_families_per_domain:
        for group in DOMAIN_GROUPS:
            group_retrieval = {
                str(case["retrieval"]["family"])
                for case in natural
                if case["domain_group"] == group
            }
            if group_retrieval != RETRIEVAL_FAMILIES:
                raise FreezeError(
                    f"Domain group {group} does not cover every retrieval family."
                )

    model_families = {str(case["generator"]["model_family"]) for case in natural}
    if policy.minimum_families_per_domain and len(model_families) < 2:
        raise FreezeError("Natural OOD requires at least two generator model families.")
    chunk_sizes = {int(case["chunking"]["size"]) for case in natural}
    if policy.minimum_families_per_domain and len(chunk_sizes) < 2:
        raise FreezeError("Natural OOD requires at least two chunk sizes.")
    reranking_states = {bool(case["reranking"]["enabled"]) for case in natural}
    if policy.minimum_families_per_domain and reranking_states != {False, True}:
        raise FreezeError("Natural OOD requires reranking enabled and disabled cases.")

    temporal_count = len(temporal)
    return {
        "natural_ood_count": natural_count,
        "temporal_source_condition_count": temporal_count,
        "source_family_count": len(families),
        "domain_groups": sorted(groups),
        "retrieval_families": sorted(retrieval_families),
        "generator_model_families": sorted(model_families),
        "chunk_sizes": sorted(chunk_sizes),
        "reranking_states": sorted(reranking_states),
        "natural_target_met": True,
        "temporal_target_met": (
            policy.temporal_target_minimum
            <= temporal_count
            <= policy.temporal_target_maximum
        ),
        "policy": {
            "minimum_natural_cases": policy.minimum_natural_cases,
            "maximum_natural_cases": policy.maximum_natural_cases,
            "minimum_source_families": policy.minimum_source_families,
            "minimum_families_per_domain": policy.minimum_families_per_domain,
            "maximum_family_fraction": policy.maximum_family_fraction,
            "temporal_target_minimum": policy.temporal_target_minimum,
            "temporal_target_maximum": policy.temporal_target_maximum,
        },
    }


def freeze_manifest(
    source_manifest: Mapping[str, Any],
    case_manifest: Mapping[str, Any],
    calibration_registry: Mapping[str, Any],
    *,
    artifact_root: Path,
    composition_policy: CompositionPolicy | None = None,
    frozen_at: str | None = None,
) -> dict[str, Any]:
    """Validate and seal an unlabeled candidate manifest."""

    _validate_schema(
        source_manifest,
        SOURCE_SCHEMA_PATH,
        label="Candidate source manifest",
    )
    _validate_schema(
        calibration_registry,
        SOURCE_SCHEMA_PATH,
        label="Calibration registry",
    )
    _validate_schema(
        case_manifest,
        CASE_SCHEMA_PATH,
        label="Candidate case manifest",
    )
    if source_manifest["manifest_kind"] != "contexttrace_unseen_v1_sources":
        raise FreezeError("Candidate source manifest has the wrong manifest_kind.")
    if calibration_registry["manifest_kind"] != "contexttrace_calibration_registry":
        raise FreezeError("Calibration registry has the wrong manifest_kind.")

    candidate_sources = source_manifest["sources"]
    calibration_sources = calibration_registry["sources"]
    if not candidate_sources:
        raise FreezeError("Candidate source manifest must contain at least one source.")
    if not calibration_sources:
        raise FreezeError(
            "Calibration registry must be populated before an untouched freeze."
        )

    _require_no_label_fields(source_manifest, label="Candidate source manifest")
    _validate_source_uniqueness(candidate_sources, label="candidate")
    _validate_source_uniqueness(calibration_sources, label="calibration")
    _validate_source_policy(candidate_sources, label="Candidate")

    dimensions = list(calibration_registry["disjoint_dimensions"])
    overlaps = _overlap_values(candidate_sources, calibration_sources, dimensions)
    if overlaps:
        raise FreezeError(
            "Candidate sources overlap calibration registry: "
            f"{canonical_json(overlaps)}"
        )

    artifact_root = artifact_root.resolve()
    if not artifact_root.is_dir():
        raise FreezeError(f"Artifact root is not a directory: {artifact_root}")
    source_artifacts = _validate_source_artifacts(
        candidate_sources,
        artifact_root=artifact_root,
    )
    cases, case_artifacts = _validate_cases(
        case_manifest,
        candidate_sources,
        artifact_root=artifact_root,
    )
    composition = _composition(
        cases,
        policy=composition_policy or CompositionPolicy(),
    )

    freeze_time = frozen_at or datetime.now(timezone.utc).isoformat()
    _parse_timestamp(freeze_time, field="frozen_at")
    sources = sorted(
        (copy.deepcopy(dict(source)) for source in candidate_sources),
        key=lambda item: item["source_id"],
    )
    artifacts = {
        path: digest
        for path, digest in sorted(
            {**source_artifacts, **case_artifacts}.items(),
        )
    }
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_frozen_unlabeled",
        "status": "frozen_unscored",
        "frozen_at": freeze_time,
        "source_count": len(sources),
        "case_count": len(cases),
        "source_manifest_sha256": canonical_sha256(source_manifest),
        "case_manifest_sha256": canonical_sha256(case_manifest),
        "calibration_registry_sha256": canonical_sha256(calibration_registry),
        "domain_ontology_version": source_manifest["domain_ontology_version"],
        "disjoint_dimensions": dimensions,
        "composition": composition,
        "sources": sources,
        "cases": cases,
        "artifacts": artifacts,
        "policy": (
            "Publish this unlabeled seal before successor implementation or label "
            "access; score the untouched set once after all locks exist."
        ),
    }
    payload["seal"] = {
        "algorithm": "sha256",
        "payload_sha256": canonical_sha256(payload),
    }
    verify_frozen_manifest(payload)
    return payload


def verify_frozen_manifest(
    manifest: Mapping[str, Any],
    *,
    expected_sha256: str | None = None,
    artifact_root: Path | None = None,
) -> str:
    """Verify a frozen manifest seal and, optionally, its artifact bytes."""

    _require_no_label_fields(manifest, label="Frozen manifest")
    if manifest.get("manifest_kind") != "contexttrace_unseen_v1_frozen_unlabeled":
        raise FreezeError("Not a ContextTrace-Unseen-v1 frozen unlabeled manifest.")
    if manifest.get("status") != "frozen_unscored":
        raise FreezeError("Frozen manifest status is not frozen_unscored.")
    seal = manifest.get("seal")
    if not isinstance(seal, dict) or seal.get("algorithm") != "sha256":
        raise FreezeError("Frozen manifest has no valid SHA-256 seal.")
    sealed_digest = seal.get("payload_sha256")
    if not isinstance(sealed_digest, str) or not SHA256_PATTERN.fullmatch(
        sealed_digest
    ):
        raise FreezeError("Frozen manifest seal digest is missing or invalid.")

    payload = copy.deepcopy(dict(manifest))
    payload.pop("seal", None)
    actual_digest = canonical_sha256(payload)
    if actual_digest != sealed_digest:
        raise FreezeError(
            "Frozen manifest was modified after sealing: expected "
            f"{sealed_digest}, got {actual_digest}"
        )
    if expected_sha256 is not None and actual_digest != expected_sha256:
        raise FreezeError(
            f"Frozen manifest does not match published hash {expected_sha256}."
        )
    if manifest.get("source_count") != len(manifest.get("sources") or []):
        raise FreezeError("Frozen manifest source_count is inconsistent.")
    if manifest.get("case_count") != len(manifest.get("cases") or []):
        raise FreezeError("Frozen manifest case_count is inconsistent.")

    if artifact_root is not None:
        root = artifact_root.resolve()
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            raise FreezeError("Frozen manifest artifacts must be an object.")
        for relative_path, digest in artifacts.items():
            _verify_file_hash(
                root,
                str(relative_path),
                str(digest),
                field="frozen artifact",
            )
    return actual_digest


def write_frozen_manifest(manifest: Mapping[str, Any], output: Path) -> str:
    digest = verify_frozen_manifest(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return digest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze or verify ContextTrace-Unseen-v1 unlabeled manifests."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--source-manifest", required=True, type=Path)
    freeze.add_argument("--case-manifest", required=True, type=Path)
    freeze.add_argument("--calibration-registry", required=True, type=Path)
    freeze.add_argument("--artifact-root", required=True, type=Path)
    freeze.add_argument("--output", required=True, type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--expected-sha256")
    verify.add_argument("--artifact-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "freeze":
        manifest = freeze_manifest(
            _load_json(args.source_manifest),
            _load_json(args.case_manifest),
            _load_json(args.calibration_registry),
            artifact_root=args.artifact_root,
        )
        digest = write_frozen_manifest(manifest, args.output)
        print(f"Frozen {manifest['case_count']} unlabeled cases: {digest}")
        return 0

    manifest = _load_json(args.manifest)
    digest = verify_frozen_manifest(
        manifest,
        expected_sha256=args.expected_sha256,
        artifact_root=args.artifact_root,
    )
    print(f"Verified frozen unlabeled manifest: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
