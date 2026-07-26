from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    BYTE_NORMALIZED_HASH,
    CASE_SCHEMA_PATH,
    SOURCE_SCHEMA_PATH,
    CompositionPolicy,
    FreezeError,
    _load_json,
    canonical_sha256,
    file_sha256,
    freeze_manifest,
    normalized_text_sha256,
    verify_frozen_manifest,
    write_frozen_manifest,
)


FIXED_HASH = "1" * 64
CREATED_AT = "2026-08-01T12:00:00+00:00"
COLLECTED_AT = "2026-08-01T09:00:00+00:00"
GENERATED_AT = "2026-08-01T10:00:00+00:00"
FROZEN_AT = "2026-08-01T13:00:00+00:00"
DISJOINT_DIMENSIONS = [
    "source_id",
    "source_document_id",
    "source_family",
    "domain_id",
    "publication_window",
    "snapshot_sha256",
    "normalized_content_sha256",
    "near_duplicate_cluster_id",
]


def _source(
    root: Path,
    *,
    source_id: str,
    document: str,
    family: str,
    domain: str,
    window: str,
    domain_group: str = "software_product_documentation",
    create_artifacts: bool = True,
) -> dict:
    snapshot_path = f"sources/{source_id}.raw"
    normalized_path = f"sources/{source_id}.txt"
    snapshot_bytes = f"<html><body>{source_id} raw source</body></html>".encode()
    normalized_text = f"{source_id} normalized source text"
    if create_artifacts:
        (root / "sources").mkdir(parents=True, exist_ok=True)
        (root / snapshot_path).write_bytes(snapshot_bytes)
        (root / normalized_path).write_text(normalized_text, encoding="utf-8")
        snapshot_sha = file_sha256(root / snapshot_path)
        normalized_sha = normalized_text_sha256(root / normalized_path)
    else:
        snapshot_sha = canonical_sha256({"source": source_id, "kind": "raw"})
        normalized_sha = canonical_sha256({"source": source_id, "kind": "normalized"})

    return {
        "source_id": source_id,
        "source_document_id": document,
        "document_lineage_id": f"lineage-{document}",
        "source_family": family,
        "domain_group": domain_group,
        "domain_id": domain,
        "publication_window": window,
        "source_url": f"https://example.test/{source_id}",
        "canonical_identifier": f"example:{source_id}",
        "snapshot_path": snapshot_path,
        "snapshot_sha256": snapshot_sha,
        "normalized_text_path": normalized_path,
        "normalized_content_sha256": normalized_sha,
        "near_duplicate_cluster_id": f"cluster-{source_id}",
        "collected_at": COLLECTED_AT,
        "published_at": "2026-07-01T00:00:00+00:00",
        "language": "en",
        "content_type": "text/html",
        "source_conditions": ["current", "canonical"],
        "authority_basis": "Official publisher.",
        "license": {
            "license_id": "CC-BY-4.0",
            "terms_url": "https://creativecommons.org/licenses/by/4.0/",
            "redistribution": "permitted",
            "attribution_required": True,
            "review_status": "approved",
            "reviewed_by": "license-reviewer",
            "reviewed_at": "2026-07-31T00:00:00+00:00",
        },
        "access": {
            "access_class": "public",
            "authentication_required": False,
            "collection_permitted": True,
            "restrictions": [],
        },
        "privacy_classification": "public",
        "metadata": {},
    }


def _source_manifest(sources: list[dict], *, calibration: bool = False) -> dict:
    return {
        "schema_version": "1.0",
        "manifest_kind": (
            "contexttrace_calibration_registry"
            if calibration
            else "contexttrace_unseen_v1_sources"
        ),
        "created_at": CREATED_AT,
        "domain_ontology_version": "cain-domain-v1",
        "disjoint_dimensions": list(DISJOINT_DIMENSIONS),
        "sources": sources,
    }


def _trace(
    root: Path, case_id: str, *, answer: str = "The feature is available."
) -> tuple[str, str, dict]:
    path = f"traces/{case_id}.json"
    payload = {
        "case_id": case_id,
        "query": "Is the feature available?",
        "answer": answer,
        "retrieved_chunks": [
            {
                "id": "chunk-1",
                "text": "The feature is available.",
                "source_id": "candidate-source",
            }
        ],
        "selected_context_ids": ["chunk-1"],
        "citations": [{"source_id": "candidate-source", "chunk_id": "chunk-1"}],
    }
    (root / "traces").mkdir(parents=True, exist_ok=True)
    (root / path).write_text(json.dumps(payload), encoding="utf-8")
    return path, file_sha256(root / path), payload


def _case(
    root: Path,
    source: dict,
    *,
    case_id: str = "case-001",
    track: str = "natural_ood",
    other_source: dict | None = None,
) -> dict:
    trace_path, trace_sha, trace = _trace(root, case_id)
    sources = [source] if other_source is None else [source, other_source]
    license_ids = sorted({item["license"]["license_id"] for item in sources})
    case = {
        "case_id": case_id,
        "track": track,
        "split": "untouched_test_candidate",
        "source_ids": [item["source_id"] for item in sources],
        "primary_source_id": source["source_id"],
        "source_family": source["source_family"],
        "source_document_id": source["source_document_id"],
        "domain_group": source["domain_group"],
        "domain_id": source["domain_id"],
        "publication_window": source["publication_window"],
        "source_url": source["source_url"],
        "canonical_identifier": source["canonical_identifier"],
        "source_snapshot_sha256": source["snapshot_sha256"],
        "retrieval": {
            "family": "bm25",
            "implementation": "test-retriever",
            "revision": "1",
            "top_k": 5,
            "configuration_sha256": canonical_sha256({"retrieval": case_id}),
        },
        "chunking": {
            "strategy": "fixed",
            "size": 512,
            "overlap": 64,
            "unit": "tokens",
            "configuration_sha256": canonical_sha256({"chunking": case_id}),
        },
        "reranking": {
            "enabled": False,
            "implementation": None,
            "revision": None,
            "top_n": None,
            "configuration_sha256": canonical_sha256({"reranking": case_id}),
        },
        "generator": {
            "provider": "local-test",
            "model": "fixture-generator",
            "model_family": "fixture-family",
            "revision": "immutable-test",
            "configuration_sha256": canonical_sha256({"generator": case_id}),
        },
        "prompt_sha256": canonical_sha256({"prompt": case_id}),
        "generation_parameters": {"temperature": 0},
        "collection_timestamp": GENERATED_AT,
        "trace_schema_version": "candidate-trace-v1",
        "license_access": {
            "license_ids": license_ids,
            "redistribution": "permitted",
        },
        "privacy_classification": "public",
        "origin": "natural_rag_run",
        "untouched_eligible": True,
        "labels_accessible_at_generation": False,
        "verifier_history": [],
        "trace_artifact_path": trace_path,
        "trace_sha256": trace_sha,
        "retrieved_chunk_ids": ["chunk-1"],
        "selected_context_ids": ["chunk-1"],
        "citation_format": "source_id",
        "answer_length_chars": len(trace["answer"]),
        "context_count": 1,
        "generation_status": "completed",
        "configuration_sha256": canonical_sha256({"case": case_id}),
        "metadata": {},
    }
    if track == "temporal_source_condition":
        assert other_source is not None
        case["source_condition_pair"] = {
            "pair_id": f"pair-{case_id}",
            "pair_type": "old_api_to_replacement_api",
            "left_source_id": source["source_id"],
            "right_source_id": other_source["source_id"],
            "authority_basis": "The right source is the documented replacement.",
        }
    return case


def _case_manifest(cases: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_cases",
        "created_at": CREATED_AT,
        "collection_protocol_version": "1.0",
        "claim_policy_version": "1.0",
        "label_access": {
            "labels_created": False,
            "labels_accessible": False,
            "first_accessed_at": None,
            "custodian": None,
        },
        "cases": cases,
    }


def _valid_bundle(root: Path) -> tuple[dict, dict, dict]:
    candidate = _source(
        root,
        source_id="candidate-source",
        document="candidate-doc",
        family="candidate-family",
        domain="candidate-domain",
        window="2026-H1",
    )
    calibration = _source(
        root,
        source_id="calibration-source",
        document="calibration-doc",
        family="calibration-family",
        domain="calibration-domain",
        window="2025-H2",
        create_artifacts=False,
    )
    case = _case(root, candidate)
    return (
        _source_manifest([candidate]),
        _case_manifest([case]),
        _source_manifest([calibration], calibration=True),
    )


def _freeze(root: Path, bundle: tuple[dict, dict, dict]) -> dict:
    sources, cases, calibration = bundle
    return freeze_manifest(
        sources,
        cases,
        calibration,
        artifact_root=root,
        composition_policy=CompositionPolicy.small_fixture(),
        frozen_at=FROZEN_AT,
    )


def _rehash_trace(root: Path, case: dict) -> None:
    case["trace_sha256"] = file_sha256(root / case["trace_artifact_path"])


def test_json_schemas_are_valid_draft_2020_12():
    Draft202012Validator.check_schema(_load_json(SOURCE_SCHEMA_PATH))
    Draft202012Validator.check_schema(_load_json(CASE_SCHEMA_PATH))


def test_freeze_sorts_records_and_has_deterministic_seal(tmp_path):
    bundle = _valid_bundle(tmp_path)
    first = _freeze(tmp_path, bundle)
    second = _freeze(tmp_path, bundle)

    assert first == second
    assert first["status"] == "frozen_unscored"
    assert first["case_count"] == 1
    assert first["source_count"] == 1
    assert first["composition"]["natural_target_met"] is True
    assert verify_frozen_manifest(first) == first["seal"]["payload_sha256"]


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("source", "snapshot_sha256"),
        ("source", "normalized_content_sha256"),
        ("case", "prompt_sha256"),
        ("case", "trace_sha256"),
        ("case", "configuration_sha256"),
    ],
)
def test_freeze_rejects_missing_required_metadata(tmp_path, section, field):
    sources, cases, calibration = _valid_bundle(tmp_path)
    target = sources["sources"][0] if section == "source" else cases["cases"][0]
    del target[field]

    with pytest.raises(FreezeError, match=field):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_duplicate_case_ids(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    duplicate = copy.deepcopy(cases["cases"][0])
    cases["cases"].append(duplicate)

    with pytest.raises(FreezeError, match="Duplicate candidate case case_id"):
        _freeze(tmp_path, (sources, cases, calibration))


@pytest.mark.parametrize("field", ["source_id", "source_document_id"])
def test_freeze_rejects_duplicate_source_identity(tmp_path, field):
    sources, cases, calibration = _valid_bundle(tmp_path)
    duplicate = _source(
        tmp_path,
        source_id="candidate-source-2",
        document="candidate-doc-2",
        family="candidate-family",
        domain="candidate-domain",
        window="2026-H1",
    )
    duplicate[field] = sources["sources"][0][field]
    sources["sources"].append(duplicate)

    with pytest.raises(FreezeError, match=f"Duplicate candidate {field}"):
        _freeze(tmp_path, (sources, cases, calibration))


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "source_document_id",
        "source_family",
        "domain_id",
        "publication_window",
        "snapshot_sha256",
        "normalized_content_sha256",
        "near_duplicate_cluster_id",
    ],
)
def test_freeze_rejects_every_calibration_overlap_dimension(tmp_path, field):
    sources, cases, calibration = _valid_bundle(tmp_path)
    calibration["sources"][0][field] = sources["sources"][0][field]

    with pytest.raises(FreezeError, match="overlap calibration registry"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_source_document_crossing_tracks(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    primary = sources["sources"][0]
    replacement = _source(
        tmp_path,
        source_id="replacement-source",
        document="replacement-doc",
        family="candidate-family",
        domain="candidate-domain",
        window="2026-H2",
    )
    sources["sources"].append(replacement)
    cases["cases"].append(
        _case(
            tmp_path,
            primary,
            case_id="case-temporal",
            track="temporal_source_condition",
            other_source=replacement,
        )
    )

    with pytest.raises(FreezeError, match="cross forbidden track boundaries"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_duplicate_content_across_forbidden_boundaries(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    duplicate = _source(
        tmp_path,
        source_id="candidate-source-2",
        document="candidate-doc-2",
        family="other-family",
        domain="other-domain",
        window="2026-H2",
    )
    duplicate["normalized_content_sha256"] = sources["sources"][0][
        "normalized_content_sha256"
    ]
    sources["sources"].append(duplicate)

    with pytest.raises(FreezeError, match="duplicates normalized_content_sha256"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_source_snapshot_hash_mismatch(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["snapshot_sha256"] = FIXED_HASH
    cases["cases"][0]["source_snapshot_sha256"] = FIXED_HASH

    with pytest.raises(FreezeError, match="hash mismatch"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_normalized_text_hash_mismatch(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["normalized_content_sha256"] = FIXED_HASH

    with pytest.raises(FreezeError, match="normalized content hash mismatch"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_missing_artifact(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    (tmp_path / cases["cases"][0]["trace_artifact_path"]).unlink()

    with pytest.raises(FreezeError, match="does not exist"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_unsafe_artifact_path(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["trace_artifact_path"] = "../outside.json"

    with pytest.raises(FreezeError, match="trace_artifact_path"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_trace_case_mismatch(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    case = cases["cases"][0]
    path = tmp_path / case["trace_artifact_path"]
    trace = json.loads(path.read_text())
    trace["case_id"] = "wrong-case"
    path.write_text(json.dumps(trace), encoding="utf-8")
    _rehash_trace(tmp_path, case)

    with pytest.raises(FreezeError, match="mismatched case_id"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_label_fields_in_trace(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    case = cases["cases"][0]
    path = tmp_path / case["trace_artifact_path"]
    trace = json.loads(path.read_text())
    trace["metadata"] = {"gold_label": "unsupported"}
    path.write_text(json.dumps(trace), encoding="utf-8")
    _rehash_trace(tmp_path, case)

    with pytest.raises(FreezeError, match="forbidden label-derived fields"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_label_fields_in_candidate_metadata(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["metadata"] = {"root_cause": "retrieval_miss"}

    with pytest.raises(FreezeError, match="forbidden label-derived fields"):
        _freeze(tmp_path, (sources, cases, calibration))


@pytest.mark.parametrize("verifier", ["semantic_core_v2", "semantic_v1_calibrated"])
def test_freeze_rejects_prior_evaluated_verifier_exposure(tmp_path, verifier):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["verifier_history"] = [
        {
            "identifier": verifier,
            "revision": "test",
            "invoked_at": GENERATED_AT,
        }
    ]

    with pytest.raises(FreezeError, match="passed through a verifier"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_case_generated_after_labels_accessible(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["labels_accessible_at_generation"] = True

    with pytest.raises(FreezeError, match="labels_accessible_at_generation"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_manifest_when_labels_already_exist(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["label_access"]["labels_created"] = True

    with pytest.raises(FreezeError, match="labels_created"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_unknown_source_reference(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["source_ids"] = ["unknown-source"]
    cases["cases"][0]["primary_source_id"] = "unknown-source"

    with pytest.raises(FreezeError, match="unknown sources"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_case_source_metadata_mismatch(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["domain_id"] = "wrong-domain"

    with pytest.raises(FreezeError, match="does not match its primary source"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_generation_before_source_collection(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["collected_at"] = "2026-08-01T11:00:00+00:00"

    with pytest.raises(FreezeError, match="before source"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_generation_after_case_manifest_creation(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["collection_timestamp"] = "2026-08-01T13:00:00+00:00"

    with pytest.raises(FreezeError, match="after manifest creation"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_unapproved_license(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["license"]["review_status"] = "pending"

    with pytest.raises(FreezeError, match="license review is not approved"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_source_that_disallows_collection(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["access"]["collection_permitted"] = False

    with pytest.raises(FreezeError, match="does not permit collection"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_restricted_source(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["access"]["access_class"] = "authorized_restricted"

    with pytest.raises(FreezeError, match="restricted"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_requires_pii_review(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    sources["sources"][0]["privacy_classification"] = "public_pii_review_required"

    with pytest.raises(FreezeError, match="required PII review"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_license_metadata_mismatch(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["license_access"]["license_ids"] = ["MIT"]

    with pytest.raises(FreezeError, match="license_ids do not match"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_invalid_chunk_overlap(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["chunking"]["overlap"] = 512

    with pytest.raises(FreezeError, match="chunk overlap"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_inconsistent_disabled_reranker(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    cases["cases"][0]["reranking"]["implementation"] = "should-be-null"

    with pytest.raises(FreezeError, match="disabled reranking"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_rejects_temporal_pair_with_unknown_pair_source(tmp_path):
    sources, _, calibration = _valid_bundle(tmp_path)
    primary = sources["sources"][0]
    replacement = _source(
        tmp_path,
        source_id="replacement-source",
        document="replacement-doc",
        family="candidate-family",
        domain="candidate-domain",
        window="2026-H2",
    )
    sources["sources"].append(replacement)
    case = _case(
        tmp_path,
        primary,
        case_id="case-temporal",
        track="temporal_source_condition",
        other_source=replacement,
    )
    case["source_condition_pair"]["right_source_id"] = "not-in-case"

    with pytest.raises(FreezeError, match="must name two case sources"):
        _freeze(
            tmp_path,
            (sources, _case_manifest([case]), calibration),
        )


def test_freeze_rejects_duplicate_trace_artifact_path(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    duplicate = copy.deepcopy(cases["cases"][0])
    duplicate["case_id"] = "case-002"
    path = tmp_path / duplicate["trace_artifact_path"]
    trace = json.loads(path.read_text())
    trace["case_id"] = "case-002"
    path.write_text(json.dumps(trace), encoding="utf-8")
    duplicate["trace_sha256"] = file_sha256(path)
    cases["cases"][0]["trace_sha256"] = duplicate["trace_sha256"]
    cases["cases"].append(duplicate)

    with pytest.raises(FreezeError, match="Duplicate trace artifact path"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_freeze_requires_populated_calibration_registry(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)
    calibration["sources"] = []

    with pytest.raises(FreezeError, match="Calibration registry must be populated"):
        _freeze(tmp_path, (sources, cases, calibration))


def test_default_composition_policy_rejects_tiny_candidate(tmp_path):
    sources, cases, calibration = _valid_bundle(tmp_path)

    with pytest.raises(FreezeError, match="Natural OOD composition"):
        freeze_manifest(
            sources,
            cases,
            calibration,
            artifact_root=tmp_path,
            frozen_at=FROZEN_AT,
        )


def test_verify_rejects_modified_manifest(tmp_path):
    manifest = _freeze(tmp_path, _valid_bundle(tmp_path))
    manifest["cases"][0]["domain_id"] = "tampered"

    with pytest.raises(FreezeError, match="modified after sealing"):
        verify_frozen_manifest(manifest)


def test_verify_rejects_wrong_published_hash(tmp_path):
    manifest = _freeze(tmp_path, _valid_bundle(tmp_path))

    with pytest.raises(FreezeError, match="published hash"):
        verify_frozen_manifest(manifest, expected_sha256=FIXED_HASH)


def test_verify_rejects_modified_artifact_bytes(tmp_path):
    manifest = _freeze(tmp_path, _valid_bundle(tmp_path))
    trace_path = tmp_path / manifest["cases"][0]["trace_artifact_path"]
    trace_path.write_text('{"tampered": true}', encoding="utf-8")

    with pytest.raises(FreezeError, match="hash mismatch"):
        verify_frozen_manifest(manifest, artifact_root=tmp_path)


def test_write_creates_verifiable_hash_sidecar(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    manifest = _freeze(artifact_root, _valid_bundle(artifact_root))
    output = tmp_path / "manifest.json"

    digest = write_frozen_manifest(manifest, output)

    assert output.is_file()
    assert output.with_suffix(".json.sha256").read_text().startswith(digest)
    assert verify_frozen_manifest(_load_json(output), expected_sha256=digest) == digest


def test_freeze_supports_explicit_byte_hash_provenance_and_uniform_audit(
    tmp_path: Path,
) -> None:
    source = _source(
        tmp_path,
        source_id="candidate-source",
        document="candidate-document",
        family="candidate-family",
        domain="candidate-domain",
        window="2026-q3",
    )
    normalized_path = tmp_path / source["normalized_text_path"]
    source["normalized_content_sha256"] = file_sha256(normalized_path)
    source["metadata"]["normalized_content_hash_kind"] = BYTE_NORMALIZED_HASH
    calibration_source = _source(
        tmp_path,
        source_id="calibration-source",
        document="calibration-document",
        family="calibration-family",
        domain="calibration-domain",
        window="2025-q1",
    )
    manifest = _freeze(
        tmp_path,
        (
            _source_manifest([source]),
            _case_manifest([_case(tmp_path, source)]),
            _source_manifest([calibration_source], calibration=True),
        ),
    )
    assert manifest["normalization_audit"]["source_count"] == 1
    assert manifest["normalization_audit"]["unique_semantic_fingerprints"] == 1
