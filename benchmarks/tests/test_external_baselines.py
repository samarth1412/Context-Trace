from __future__ import annotations

import hashlib
import json
import zipfile
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
from benchmarks.external_baselines.run_minicheck import (
    MiniCheckAuditError,
    _audit_files,
    project_minicheck_labels,
)
from benchmarks.external_baselines.run_minicheck import (
    _existing_rows_for_run as minicheck_existing_rows_for_run,
)
from benchmarks.external_baselines.run_refchecker import (
    RefCheckerAuditError,
    _audit_installed_wheel,
    project_refchecker_labels,
    reference_passages,
)
from benchmarks.external_baselines.run_refchecker import (
    _existing_rows_for_run as refchecker_existing_rows_for_run,
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


def test_audit_rejects_output_marked_incomplete(tmp_path: Path) -> None:
    lock_path, artifact_root = _write_ragas_fixture(tmp_path)
    raw_path = artifact_root / "raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["complete"] = False
    _write_json(raw_path, raw)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["comparisons"][0]["baseline_raw"]["sha256"] = _sha256(raw_path)
    _write_json(lock_path, lock)

    with pytest.raises(BaselineAuditError, match="marked incomplete"):
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
    assert _project_labels(
        {"should_have_abstained"},
        dataset="RAGTruth",
        claim_verdicts={"supported", "contradicted"},
    ) == {"contradicted_answer"}
    assert _project_labels(
        {"should_have_abstained"},
        dataset="RAGTruth",
        claim_verdicts={"supported", "unverifiable"},
    ) == {"partial_support"}
    assert _project_labels(
        {"no_failure_detected"},
        dataset="RAGTruth",
        claim_verdicts={"supported"},
    ) == {"no_failure_detected"}
    assert _project_labels(
        {"should_have_abstained"},
        dataset="RAGTruth",
        claim_verdicts={"unsupported"},
    ) == {"unsupported"}
    assert (
        _project_root({"should_have_abstained", "unsupported_answer"})
        == "should_have_abstained"
    )


def test_artifact_path_cannot_escape_root(tmp_path: Path) -> None:
    with pytest.raises(BaselineAuditError, match="escapes"):
        _resolve_artifact(tmp_path, "../outside.json")


def test_minicheck_projection_preserves_binary_scope() -> None:
    assert project_minicheck_labels([1, 1], dataset="RAGTruth") == (
        ["no_failure_detected"],
        "no_failure_detected",
    )
    assert project_minicheck_labels([0, 0], dataset="RAGTruth") == (
        ["unsupported"],
        "answer_overreach",
    )
    assert project_minicheck_labels([1, 0], dataset="RAGTruth") == (
        ["partial_support"],
        "answer_overreach",
    )
    assert project_minicheck_labels([0], dataset="ARES-NQ-example") == (
        ["should_have_abstained", "unsupported_answer"],
        "should_have_abstained",
    )
    assert project_minicheck_labels([0], dataset="CRAG-Task1-v5") == (
        ["unsupported_answer"],
        "answer_overreach",
    )


def test_minicheck_artifact_audit_fails_closed(tmp_path: Path) -> None:
    model_file = tmp_path / "config.json"
    model_file.write_text("locked", encoding="utf-8")
    expected = {"config.json": hashlib.sha256(b"locked").hexdigest()}

    assert _audit_files(tmp_path, expected, artifact_name="fixture") == expected
    model_file.write_text("changed", encoding="utf-8")
    with pytest.raises(MiniCheckAuditError, match="SHA-256 mismatch"):
        _audit_files(tmp_path, expected, artifact_name="fixture")


@pytest.mark.parametrize(
    ("resolver", "error_type"),
    [
        (minicheck_existing_rows_for_run, MiniCheckAuditError),
        (refchecker_existing_rows_for_run, RefCheckerAuditError),
    ],
)
def test_competitor_runner_refuses_silent_checkpoint_overwrite(
    tmp_path: Path,
    resolver: object,
    error_type: type[Exception],
) -> None:
    output = tmp_path / "checkpoint.json"
    output.write_text("{}\n", encoding="utf-8")

    with pytest.raises(error_type, match="Refusing to overwrite"):
        resolver(  # type: ignore[operator]
            output,
            resume=False,
            expected_runtime={},
            dataset="fixture",
        )


def test_refchecker_wheel_audit_binds_installed_package(tmp_path: Path) -> None:
    wheel = tmp_path / "refchecker-0.2.17-py3-none-any.whl"
    package_file = tmp_path / "installed" / "refchecker" / "module.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("PINNED = True\n", encoding="utf-8")
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("refchecker/module.py", "PINNED = True\n")
    lock = {"package_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}

    audited = _audit_installed_wheel(
        lock,
        wheel,
        install_root=package_file.parents[1],
    )
    assert audited == {
        "refchecker/module.py": hashlib.sha256(b"PINNED = True\n").hexdigest()
    }

    package_file.write_text("PINNED = False\n", encoding="utf-8")
    with pytest.raises(RefCheckerAuditError, match="file changed"):
        _audit_installed_wheel(
            lock,
            wheel,
            install_root=package_file.parents[1],
        )


def test_refchecker_projection_preserves_three_way_scope() -> None:
    assert project_refchecker_labels(["Entailment"], dataset="RAGTruth") == (
        ["no_failure_detected"],
        "no_failure_detected",
    )
    assert project_refchecker_labels(
        ["Entailment", "Contradiction"], dataset="RAGTruth"
    ) == (["contradicted_answer"], "conflicting_contexts")
    assert project_refchecker_labels(["Neutral"], dataset="RAGTruth") == (
        ["unsupported"],
        "answer_overreach",
    )
    assert project_refchecker_labels(["Entailment", "Neutral"], dataset="RAGTruth") == (
        ["partial_support"],
        "answer_overreach",
    )
    assert project_refchecker_labels(["Neutral"], dataset="ARES-NQ-example") == (
        ["should_have_abstained", "unsupported_answer"],
        "should_have_abstained",
    )


def test_refchecker_preserves_retrieved_passage_boundaries() -> None:
    trace = {
        "contexts": [
            {"id": "first", "text": "First passage."},
            {"id": "second", "text": "Second passage."},
        ]
    }

    assert reference_passages(trace) == ["First passage.", "Second passage."]


def test_minicheck_adapter_preserves_native_verdict_counts() -> None:
    candidate = adapt_candidate_rows(
        [
            {
                "id": "case-1",
                "predicted_labels": ["partial_support"],
                "claim_verdicts": ["supported", "unsupported"],
                "verdict_counts": {
                    "supported": 1,
                    "partially_supported": 0,
                    "unsupported": 1,
                    "contradicted": 0,
                    "unverifiable": 0,
                },
                "predicted_primary_root_cause": "answer_overreach",
            }
        ],
        system="MiniCheck",
        version="fixture",
        preset="minicheck",
    )

    prediction = candidate["predictions"][0]
    assert prediction["predicted"] == ["partial_support"]
    assert prediction["predicted_verdict_counts"]["unsupported"] == 1
    assert prediction["predicted_primary_root_cause"] == "answer_overreach"


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
