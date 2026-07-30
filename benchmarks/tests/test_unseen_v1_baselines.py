from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.baselines.contract import (
    BaselineInputError,
    build_candidate_input,
    verify_manifest_identity,
)
from benchmarks.contexttrace_unseen_v1.baselines.lexical_overlap import (
    _claim_spans,
    score_candidate,
)
from benchmarks.contexttrace_unseen_v1.baselines.reference_free_exports import (
    export_deepeval,
    export_ragas,
    export_ragchecker,
)
from benchmarks.contexttrace_unseen_v1.baselines.semantic_v1_adapter import (
    FACTS_SOURCE_SHA256,
    prepare_trace,
)


ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = ROOT / "benchmarks" / "contexttrace_unseen_v1"


def _case() -> dict[str, object]:
    return {
        "case_id": "case-1",
        "track": "natural_ood",
        "retrieved_chunk_ids": ["source/chunk-1", "source/chunk-2"],
        "selected_context_ids": ["source/chunk-2"],
    }


def _trace() -> dict[str, object]:
    return {
        "case_id": "case-1",
        "query": "What is the current limit?",
        "answer": "The limit is ten [source/chunk-2].",
        "retrieved_chunks": [
            {
                "id": "source/chunk-1",
                "source_id": "source",
                "text": "An unrelated introduction.",
            },
            {
                "id": "source/chunk-2",
                "source_id": "source",
                "text": "The current limit is ten.",
            },
        ],
    }


def test_candidate_contract_preserves_exact_identity_and_order() -> None:
    candidate = build_candidate_input(_case(), _trace())
    assert candidate["case_id"] == "case-1"
    assert [row["chunk_id"] for row in candidate["retrieved_chunks"]] == [
        "source/chunk-1",
        "source/chunk-2",
    ]
    assert [row["chunk_id"] for row in candidate["selected_contexts"]] == [
        "source/chunk-2"
    ]
    assert len(candidate["candidate_input_sha256"]) == 64


def test_candidate_contract_rejects_case_identity_change() -> None:
    trace = _trace()
    trace["case_id"] = "different"
    with pytest.raises(BaselineInputError, match="identity mismatch"):
        build_candidate_input(_case(), trace)


def test_candidate_contract_rejects_retrieval_reordering() -> None:
    trace = _trace()
    trace["retrieved_chunks"] = list(reversed(trace["retrieved_chunks"]))
    with pytest.raises(BaselineInputError, match="identity/order mismatch"):
        build_candidate_input(_case(), trace)


def test_candidate_contract_rejects_missing_selected_context() -> None:
    case = _case()
    case["selected_context_ids"] = ["source/missing"]
    with pytest.raises(BaselineInputError, match="absent from retrieval"):
        build_candidate_input(case, _trace())


def test_lexical_baseline_is_continuous_and_does_not_invent_diagnoses() -> None:
    result = score_candidate(build_candidate_input(_case(), _trace()))
    assert result["status"] == "completed"
    assert result["execution_class"] == "local_deterministic"
    assert result["cost_usd"] == 0.0
    assert result["model_calls"] == 0
    assert result["failure_label"] is None
    assert result["root_cause"] is None
    assert result["unsupported_outputs"] == ["failure_label", "root_cause"]
    assert result["scores"]["mean_claim_token_coverage"] > 0


def test_lexical_output_hash_excludes_wall_clock_latency() -> None:
    candidate = build_candidate_input(_case(), _trace())
    first = score_candidate(candidate)
    second = score_candidate(candidate)
    assert first["output_payload_sha256"] == second["output_payload_sha256"]


def test_claim_offsets_survive_citation_removal() -> None:
    answer = "First fact [source/chunk-2]. Second fact."
    spans = _claim_spans(answer)
    assert len(spans) == 2
    assert answer[spans[0][0] : spans[0][1]] == "First fact"
    assert answer[spans[1][0] : spans[1][1]] == "Second fact"


def test_reference_free_exports_never_supply_gold() -> None:
    candidate = build_candidate_input(_case(), _trace())
    ragas = export_ragas(candidate)
    deepeval = export_deepeval(candidate)
    assert ragas["case_id"] == deepeval["case_id"] == "case-1"
    assert ragas["reference"] is None
    assert deepeval["expected_output"] is None
    assert ragas["retrieved_contexts"] == deepeval["retrieval_context"]


def test_semantic_v1_adapter_preserves_candidate_identity_and_citations() -> None:
    candidate = build_candidate_input(_case(), _trace())
    trace = prepare_trace(candidate)
    assert trace.metadata["case_id"] == candidate["case_id"]
    assert trace.metadata["candidate_input_sha256"] == candidate["candidate_input_sha256"]
    assert [context.id for context in trace.contexts] == ["source/chunk-2"]
    assert [citation.source_id for citation in trace.citations] == ["source/chunk-2"]


def test_semantic_v1_frozen_source_hash_is_unchanged() -> None:
    facts = (
        ROOT
        / "packages"
        / "contexttrace"
        / "contexttrace"
        / "verify"
        / "facts.py"
    )
    assert hashlib.sha256(facts.read_bytes()).hexdigest() == FACTS_SOURCE_SHA256


def test_ragchecker_refuses_reference_free_execution() -> None:
    candidate = build_candidate_input(_case(), _trace())
    with pytest.raises(BaselineInputError, match="ground-truth answer"):
        export_ragchecker(candidate)


def test_manifest_identity_lock_rejects_wrong_hash() -> None:
    cases = [{"case_id": f"case-{index}"} for index in range(493)]
    manifest = {
        "seal": {"payload_sha256": "a" * 64},
        "cases": cases,
    }
    assert len(
        verify_manifest_identity(manifest, expected_payload_sha256="a" * 64)
    ) == 493
    with pytest.raises(BaselineInputError, match="does not match"):
        verify_manifest_identity(manifest, expected_payload_sha256="b" * 64)


def test_version_lock_matches_adapter_source_hashes() -> None:
    lock = json.loads(
        (BASELINE_ROOT / "BASELINE_VERSION_LOCK.json").read_text(encoding="utf-8")
    )
    expected_files = {
        path.name
        for path in (BASELINE_ROOT / "baselines").glob("*.py")
    }
    assert set(lock["adapter_source_hashes"]) == expected_files
    for filename, expected in lock["adapter_source_hashes"].items():
        actual = hashlib.sha256(
            (BASELINE_ROOT / "baselines" / filename).read_bytes()
        ).hexdigest()
        assert actual == expected


def test_version_lock_matches_public_freeze_record() -> None:
    lock = json.loads(
        (BASELINE_ROOT / "BASELINE_VERSION_LOCK.json").read_text(encoding="utf-8")
    )
    freeze = json.loads(
        (BASELINE_ROOT / "two_track_freeze_record.json").read_text(encoding="utf-8")
    )
    assert (
        lock["frozen_manifest_payload_sha256"]
        == freeze["artifact_chain"]["frozen_manifest_payload_sha256"]
    )


@pytest.mark.parametrize(
    ("filename", "field"),
    [
        ("BASELINE_VERSION_LOCK.json", "lock_payload_sha256"),
        ("BASELINE_RUN_RECORD.json", "record_payload_sha256"),
    ],
)
def test_baseline_records_have_valid_payload_hashes(
    filename: str,
    field: str,
) -> None:
    record = json.loads((BASELINE_ROOT / filename).read_text(encoding="utf-8"))
    expected = record.pop(field)
    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == expected


def test_private_raw_output_hashes_match_run_record_when_present() -> None:
    record = json.loads(
        (BASELINE_ROOT / "BASELINE_RUN_RECORD.json").read_text(encoding="utf-8")
    )
    private_root = ROOT / record["private_output_root"]
    if not private_root.is_dir():
        pytest.skip("Private unscored baseline outputs are intentionally not in Git.")
    for run in record["runs"]:
        raw = private_root / run["raw_output_path"]
        assert raw.stat().st_size == run["raw_output_bytes"]
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == run[
            "raw_output_file_sha256"
        ]
