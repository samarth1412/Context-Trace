from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_bench.adapt_candidate import adapt_candidate_rows
from benchmarks.external_baselines.run_comparison import (
    BaselineAuditError,
    _project_labels,
    _project_root,
    _resolve_artifact,
    audit_matrix,
)


def test_audit_accepts_complete_hash_locked_same_id_ragas_artifacts(
    tmp_path: Path,
) -> None:
    lock_path, artifact_root = _write_ragas_fixture(tmp_path)

    result = audit_matrix(lock_path, artifact_root)

    comparison = result["comparisons"][0]
    assert result["status"] == "ready"
    assert comparison["exact_id_coverage"] is True
    assert comparison["candidate_regenerates_from_raw"] is True
    assert comparison["raw_input_binding"] == ("exact_ids_and_retrieved_context_counts")


def test_audit_fails_closed_when_locked_artifact_changes(tmp_path: Path) -> None:
    lock_path, artifact_root = _write_ragas_fixture(tmp_path)
    (artifact_root / "raw.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(BaselineAuditError, match="SHA-256 mismatch"):
        audit_matrix(lock_path, artifact_root)


def test_audit_rejects_partial_or_duplicate_coverage(tmp_path: Path) -> None:
    lock_path, artifact_root = _write_ragas_fixture(tmp_path)
    raw_path = artifact_root / "raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["rows"].append(dict(raw["rows"][0]))
    _write_json(raw_path, raw)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["comparisons"][0]["baseline_raw"]["sha256"] = _sha256(raw_path)
    _write_json(lock_path, lock)

    with pytest.raises(BaselineAuditError, match="duplicate IDs"):
        audit_matrix(lock_path, artifact_root)


def test_dataset_projection_is_explicit_and_narrow() -> None:
    assert _project_labels({"should_have_abstained"}, dataset="RAGTruth") == {
        "partial_support"
    }
    assert _project_labels(
        {"contradicted_answer", "should_have_abstained"},
        dataset="RAGTruth",
    ) == {"contradicted_answer"}
    assert _project_labels({"unsupported_answer"}, dataset="ARES-NQ-example") == {
        "should_have_abstained",
        "unsupported_answer",
    }
    assert _project_labels({"unsupported_answer"}, dataset="CRAG-Task1-v5") == {
        "unsupported_answer"
    }
    assert (
        _project_root({"should_have_abstained", "unsupported_answer"})
        == "should_have_abstained"
    )


def test_artifact_path_cannot_escape_root(tmp_path: Path) -> None:
    with pytest.raises(BaselineAuditError, match="escapes"):
        _resolve_artifact(tmp_path, "../outside.json")


def _write_ragas_fixture(tmp_path: Path) -> tuple[Path, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    case_id = "case-1"
    trace = {
        "query": "What is the status?",
        "answer": "The service is active.",
        "contexts": [{"id": "doc-1", "text": "The service is active.", "metadata": {}}],
    }
    case_pack = {
        "cases": [
            {
                "id": case_id,
                "expected_labels": ["no_failure_detected"],
                "expected_primary_root_cause": "no_failure_detected",
                "expected_verdict_scope": "answer_label",
            }
        ]
    }
    candidate_inputs = [{"id": case_id, "trace": trace}]
    raw = {
        "rows": [
            {
                "id": case_id,
                "faithfulness": 1.0,
                "retrieved_context_count": 1,
            }
        ]
    }
    candidate = adapt_candidate_rows(
        raw["rows"],
        system="RAGAS",
        version="fixture",
        preset="ragas",
    )
    case_pack_path = artifact_root / "case-pack.json"
    candidate_inputs_path = artifact_root / "inputs.jsonl"
    raw_path = artifact_root / "raw.json"
    candidate_path = artifact_root / "candidate.json"
    _write_json(case_pack_path, case_pack)
    candidate_inputs_path.write_text(
        json.dumps(candidate_inputs[0], sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_json(raw_path, raw)
    _write_json(candidate_path, candidate)
    lock = {
        "schema_version": "1.0",
        "evidence_class": "test_fixture",
        "systems": [],
        "comparisons": [
            {
                "id": "fixture-ragas",
                "dataset": "RAGTruth",
                "evaluation_kind": "visible_label_accuracy",
                "expected_cases": 1,
                "baseline_system": "RAGAS",
                "baseline_version": "fixture",
                "adapter_preset": "ragas",
                "case_pack": _artifact_lock(case_pack_path),
                "candidate_inputs": _artifact_lock(candidate_inputs_path),
                "baseline_raw": _artifact_lock(raw_path),
                "baseline_candidate": _artifact_lock(candidate_path),
            }
        ],
    }
    lock_path = tmp_path / "lock.json"
    _write_json(lock_path, lock)
    return lock_path, artifact_root


def _artifact_lock(path: Path) -> dict[str, str]:
    return {"path": path.name, "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
