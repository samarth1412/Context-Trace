import json

import numpy as np
import pytest

from benchmarks.contexttrace_unseen_v2.build_corpus import (
    DEFAULT_CATALOG,
    Chunk,
    CorpusBuildError,
    _canonical_sha256,
    _contains_label_key,
    _directory_manifest_sha256,
    _parse_questions,
    _question_response_schema,
    _validate_boundaries,
    _validate_completed_case,
)


def test_source_catalog_has_frozen_disjoint_composition() -> None:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    natural = catalog["natural_sources"]
    pairs = catalog["temporal_pairs"]

    assert len(natural) == 30
    assert len(pairs) == 20
    assert {source["publication_window"] for source in natural} == {"2026-H2"}
    assert {source["domain_group"] for source in natural} == {
        "software_product",
        "support_operational",
        "policy_regulatory",
    }
    assert len({source["source_family"] for source in natural}) == 30
    assert len({pair["domain_id"] for pair in pairs}) == 20


def test_validate_boundaries_rejects_development_overlap() -> None:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    candidate = {
        "status": "candidate_frozen_before_unseen_v2_acquisition",
        "boundaries": {
            "labels_created": False,
            "candidate_executed_on_unseen_v2": False,
        },
    }
    candidate["freeze_payload_sha256"] = _canonical_sha256(candidate)
    development = {
        "sources": [{"source_family": catalog["natural_sources"][0]["source_family"]}],
        "cases": [],
    }
    development["seal"] = {
        "payload_sha256": _canonical_sha256(development),
    }

    with pytest.raises(CorpusBuildError, match="Source-family overlap"):
        _validate_boundaries(catalog, candidate, development)


def test_question_parser_requires_exact_distinct_questions() -> None:
    payload = json.dumps(
        [f"What does documented setting {index} control?" for index in range(5)]
    )

    assert len(_parse_questions(payload, count=5)) == 5
    assert _parse_questions('["Too short?"]', count=5) == []


def test_question_response_schema_freezes_exact_count() -> None:
    schema = _question_response_schema(10)

    assert schema["minItems"] == 10
    assert schema["maxItems"] == 10
    assert schema["items"]["pattern"] == r"^.*\?$"


def test_label_scan_is_recursive_but_allows_null_transport_slot() -> None:
    assert _contains_label_key({"nested": {"failure_label": "x"}})
    assert _contains_label_key({"labels": []})
    assert _contains_label_key({"labels": None})
    assert not _contains_label_key({"labels": None}, allow_null_labels=True)


def test_chunk_type_accepts_dense_ranking_fixture() -> None:
    chunks = [
        Chunk(id="c1", source_id="s", document_path="d", index=0, text="alpha"),
        Chunk(id="c2", source_id="s", document_path="d", index=1, text="beta"),
    ]
    scores = np.asarray([0.1, 0.9])

    assert chunks[int(scores.argmax())].id == "c2"


def test_model_manifest_hashes_files_below_a_cache_named_parent(tmp_path) -> None:
    model = tmp_path / ".cache" / "model"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}\n", encoding="utf-8")

    assert _directory_manifest_sha256(model) != _canonical_sha256([])


def test_resume_rejects_trace_hash_drift(tmp_path) -> None:
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    trace = trace_root / "case-1.json"
    trace.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "track": "natural_ood",
                "verifier_history": [],
            }
        ),
        encoding="utf-8",
    )
    row = {
        "case_id": "case-1",
        "track": "natural_ood",
        "source_ids": ["source-1"],
        "trace_artifact_path": "traces/case-1.json",
        "trace_sha256": "wrong",
    }

    with pytest.raises(CorpusBuildError, match="trace hash mismatch"):
        _validate_completed_case(
            row,
            case_id="case-1",
            track="natural_ood",
            source_ids=["source-1"],
            trace_root=trace_root,
        )
