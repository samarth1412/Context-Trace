from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1 import collect_temporal
from benchmarks.contexttrace_unseen_v1.collect_natural_ood import (
    Chunk,
    CollectionError,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks/contexttrace_unseen_v1"
SCHEDULE = json.loads(
    (BASE / "temporal_generation_schedule.json").read_text(encoding="utf-8")
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def test_authorization_record_is_exact_and_narrow() -> None:
    value = json.loads(
        (BASE / "temporal_run_authorization.json").read_text(encoding="utf-8")
    )
    assert (
        value["authorized_schedule_sha256"]
        == collect_temporal.AUTHORIZED_SCHEDULE_SHA256
    )
    assert (
        value["project_owner_statement"]
        == collect_temporal.EXACT_OWNER_STATEMENT
    )
    assert value["hard_ceiling_usd"] == 3.0
    assert value["authorized_scope"] == {
        "answer_generation_slots": 100,
        "annotation": False,
        "evaluation": False,
        "permitted_transport_retries": True,
        "publication": False,
        "query_editing": False,
        "release": False,
        "source_substitution": False,
        "verifier_or_nli_calls": False,
    }


def test_preflight_rejects_any_other_authorization_hash(tmp_path: Path) -> None:
    with pytest.raises(CollectionError, match="CLI authorization hash"):
        collect_temporal.preflight(
            project_root=ROOT,
            acquisition_root=tmp_path,
            collection_root=tmp_path / "out",
            authorized_schedule_sha256="0" * 64,
            require_hosted=False,
        )


def test_preflight_accepts_only_frozen_inputs_without_model_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_temporal,
        "validate_offline",
        lambda **_: {"status": "valid", "source_count": 37, "pair_count": 20},
    )
    monkeypatch.setattr(
        collect_temporal,
        "verify_environment",
        lambda *_, **__: {"hosted_key_present": False},
    )
    schedule, sources, catalog, record = collect_temporal.preflight(
        project_root=ROOT,
        acquisition_root=tmp_path,
        collection_root=tmp_path / "out",
        authorized_schedule_sha256=collect_temporal.AUTHORIZED_SCHEDULE_SHA256,
        require_hosted=False,
    )
    assert len(schedule["cases"]) == 100
    assert len(sources["sources"]) == 37
    assert len(catalog["pairs"]) == 20
    assert record["answer_generation_slots"] == 100
    assert record["query_authoring_calls"] == 0
    assert record["verifier_or_nli_calls"] == 0


def test_mixed_pool_ties_follow_frozen_source_order() -> None:
    runner = object.__new__(collect_temporal.TemporalCollectionRunner)
    runner.source_index = {
        "left": {"source_id": "left"},
        "right": {"source_id": "right"},
    }
    chunks = {
        "left": [Chunk("left/chunk-000000", "same", "left.md", 0)],
        "right": [Chunk("right/chunk-000000", "same", "right.md", 0)],
    }
    runner.source_chunks = lambda source, _chunking: chunks[source["source_id"]]
    runner.embedding_cache = None
    rankable, canonical, embeddings = runner._rankable_pool(
        {"candidate_source_ids_in_tie_order": ["right", "left"]},
        {},
        {"family": "bm25"},
    )
    assert [chunk.id for chunk in rankable] == [
        "pool-00/right/chunk-000000",
        "pool-01/left/chunk-000000",
    ]
    assert [chunk.id for chunk in canonical] == [
        "right/chunk-000000",
        "left/chunk-000000",
    ]
    assert embeddings is None


def _failure_only_collection(output_root: Path) -> None:
    for case in SCHEDULE["cases"]:
        _write_json(
            output_root / "records" / f"{case['case_id']}.json",
            {
                "schema_version": "1.0",
                "case_id": case["case_id"],
                "configuration_sha256": case["configuration_sha256"],
                "schedule_sha256": (
                    collect_temporal.AUTHORIZED_SCHEDULE_SHA256
                ),
                "status": "collection_failure",
                "query": case["question_plan"]["query"],
                "query_sha256": case["question_plan"]["query_sha256"],
                "attempts": [],
                "failed_stage": "retrieval_structure",
                "failure_type": "synthetic_test_fixture_only",
            },
        )
    _write_json(
        output_root / "candidate_case_manifest.json",
        {
            "schema_version": "1.0",
            "manifest_kind": "contexttrace_unseen_v1_cases",
            "created_at": "2026-07-26T00:00:00Z",
            "collection_protocol_version": (
                collect_temporal.COLLECTION_PROTOCOL_VERSION
            ),
            "claim_policy_version": "contexttrace-unseen-claim-policy-v1",
            "label_access": {
                "labels_created": False,
                "labels_accessible": False,
                "first_accessed_at": None,
                "custodian": None,
            },
            "cases": [],
        },
    )
    _write_json(
        output_root / "budget_ledger.json",
        {
            "schema_version": "1.0",
            "record_kind": "contexttrace_unseen_v1_hosted_budget",
            "schedule_sha256": collect_temporal.AUTHORIZED_SCHEDULE_SHA256,
            "hard_limit_usd": 3.0,
            "attempts": [],
        },
    )


def test_structural_validation_accepts_terminal_failures_without_labels(
    tmp_path: Path,
) -> None:
    _failure_only_collection(tmp_path)
    result = collect_temporal.validate_collection(
        schedule=SCHEDULE,
        output_root=tmp_path,
        schema_path=BASE / "case_manifest.schema.json",
    )
    assert result["terminal_slots"] == 100
    assert result["completed_cases"] == 0
    assert len(result["collection_failures"]) == 100
    assert result["evaluation_performed"] is False


def test_structural_validation_rejects_frozen_query_edit(
    tmp_path: Path,
) -> None:
    _failure_only_collection(tmp_path)
    first = SCHEDULE["cases"][0]
    path = tmp_path / "records" / f"{first['case_id']}.json"
    state = json.loads(path.read_text())
    state["query"] += " edited"
    _write_json(path, state)
    with pytest.raises(CollectionError, match="Frozen state mismatch"):
        collect_temporal.validate_collection(
            schedule=SCHEDULE,
            output_root=tmp_path,
            schema_path=BASE / "case_manifest.schema.json",
        )


def test_structural_validation_rejects_query_or_verifier_attempt(
    tmp_path: Path,
) -> None:
    _failure_only_collection(tmp_path)
    first = SCHEDULE["cases"][0]
    path = tmp_path / "records" / f"{first['case_id']}.json"
    state = json.loads(path.read_text())
    state["attempts"] = [
        {
            "stage": "query",
            "attempt_number": 1,
            "status": "completed",
            "provider": "Ollama",
        }
    ]
    _write_json(path, state)
    with pytest.raises(CollectionError, match="Unauthorized"):
        collect_temporal.validate_collection(
            schedule=SCHEDULE,
            output_root=tmp_path,
            schema_path=BASE / "case_manifest.schema.json",
        )


def test_cli_exposes_no_pilot_or_case_limit() -> None:
    help_text = collect_temporal.build_parser().format_help()
    assert "--case-limit" not in help_text
    assert "--pilot" not in help_text


def test_collector_has_no_verifier_package_import() -> None:
    module = (
        BASE / "collect_temporal.py"
    ).read_text(encoding="utf-8")
    assert "from contexttrace" not in module
    assert "import contexttrace" not in module
    assert "semantic_core_v2" not in module
