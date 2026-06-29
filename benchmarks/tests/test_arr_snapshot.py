from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_bench.arr_ablation import render_ablation_table
from benchmarks.contexttrace_bench.arr_snapshot import write_pre_review_snapshot
from benchmarks.contexttrace_bench.reproduce_arr_tables import (
    render_error_analysis_table,
    render_external_results_table,
)


def test_pre_review_snapshot_binds_full_outputs_and_uses_ragtruth_by_id(tmp_path):
    reproduction_dir, inputs = _write_full_reproduction_fixture(tmp_path)

    snapshot = write_pre_review_snapshot(
        reproduction_dir=reproduction_dir,
        json_path=tmp_path / "status.json",
        markdown_path=tmp_path / "status.md",
    )

    assert snapshot["paper_result_eligible"] is False
    assert snapshot["broad_sota_claim_allowed"] is False
    assert snapshot["ablation_case_ids_sha256"] == "a" * 64
    artifact_paths = {row["path"].replace("\\", "/") for row in snapshot["source_artifacts"]}
    assert any(path.endswith("runs/ragtruth/results.json") for path in artifact_paths)
    assert any(path.endswith("runs/ragtruth/baseline.json") for path in artifact_paths)
    assert all(len(row["sha256"]) == 64 for row in snapshot["source_artifacts"])
    markdown = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "| ContextTrace | 200 | 0.955" in markdown
    assert "Broad SOTA claim allowed: `False`" in markdown
    assert inputs["selected"].name in json.dumps(snapshot["inputs"])


def test_pre_review_snapshot_rejects_changed_input(tmp_path):
    reproduction_dir, inputs = _write_full_reproduction_fixture(tmp_path)
    inputs["selected"].write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="byte count changed|SHA-256 changed"):
        write_pre_review_snapshot(
            reproduction_dir=reproduction_dir,
            json_path=tmp_path / "status.json",
            markdown_path=tmp_path / "status.md",
        )


def test_pre_review_snapshot_rejects_completed_review_gate(tmp_path):
    reproduction_dir, _ = _write_full_reproduction_fixture(tmp_path)
    manifest_path = reproduction_dir / "reproduction_manifest.json"
    manifest = _read(manifest_path)
    manifest["eligibility_gates"]["independent_ragtruth_review_complete"] = True
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="independent_ragtruth_review_complete"):
        write_pre_review_snapshot(
            reproduction_dir=reproduction_dir,
            json_path=tmp_path / "status.json",
            markdown_path=tmp_path / "status.md",
        )


def test_full_table_footers_remain_pre_review_claim_safe():
    assert "full estimates remain pre-review" in render_external_results_table([], quick=False)
    assert "full-run clusters remain pre-review" in render_error_analysis_table({}, quick=False)
    assert "pre-review paper candidate" in render_ablation_table({"profiles": [], "quick": False})


def _write_full_reproduction_fixture(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    reproduction_dir = tmp_path / "reproduction"
    reproduction_dir.mkdir()
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir()
    experiment = _write_text(inputs_dir / "experiments.json", "{}")
    selected = _write_text(inputs_dir / "ragtruth.json", '{"cases": []}')
    candidate = _write_text(inputs_dir / "candidate.json", '{"predictions": []}')

    interval = {"low": 0.9, "high": 1.0, "samples": 400, "seed": 20260612}
    ragtruth_summary = {
        "cases": 200,
        "failure_label_macro_f1": 0.955,
        "claim_verdict_macro_f1": 0.337,
        "root_cause_accuracy": 0.955,
        "citation_error_f1": 1.0,
        "evidence_span_overlap": 0.786,
        "dangerous_false_green_rate": 0.0,
    }
    diag_summary = {**ragtruth_summary, "cases": 150, "failure_label_macro_f1": 1.0}
    external = [
        {
            "dataset": "ContextTrace-Diag-150",
            "dataset_id": "diag150_primary",
            "review_status": "pending_independent",
            "summary": diag_summary,
            "confidence_intervals": {"failure_label_macro_f1": interval},
        },
        {
            "dataset": "RAGTruth",
            "dataset_id": "ragtruth_primary",
            "review_status": "assisted_review_pending_independent",
            "summary": ragtruth_summary,
            "confidence_intervals": {"failure_label_macro_f1": interval},
        },
    ]
    profile_ids = ["a%s" % index for index in range(6)]
    profiles = [
        {
            "id": profile_id,
            "label": profile_id,
            "reported_summary": {"cases": 500, "failure_label_macro_f1": 0.5},
            "confidence_intervals": {"failure_label_macro_f1": interval},
        }
        for profile_id in profile_ids
    ]
    baseline = {
        "system": "RAGAS",
        "summary": {"cases": 200, "failure_label_macro_f1": 0.152},
        "confidence_intervals": {"failure_label_macro_f1": interval},
        "coverage": {
            "reference_cases": 200,
            "submitted_predictions": 200,
            "matched_predictions": 200,
        },
    }
    tables = {
        "external_results": external,
        "ablation_results": profiles,
        "baseline_results": [baseline],
        "error_analysis": {"case_count": 200, "label_miss_count": 9},
    }
    tables_path = reproduction_dir / "arr_tables.json"
    _write_json(tables_path, tables)

    ablation_dir = reproduction_dir / "ablations"
    ablation_dir.mkdir()
    ablation_results_path = ablation_dir / "ablation_results.json"
    _write_json(
        ablation_results_path,
        {
            "quick": False,
            "paper_run_candidate": True,
            "paper_result_eligible": False,
            "case_count": 500,
            "case_ids_sha256": "a" * 64,
            "bootstrap_samples": 400,
            "bootstrap_seed": 20260612,
            "profiles": profiles,
        },
    )
    ablation_matrix = _write_text(ablation_dir / "matrix.json", "{}")
    ablation_table = _write_text(ablation_dir / "table.md", "# Ablations\n")
    ragtruth_result = _write_text(reproduction_dir / "runs/ragtruth/results.json", "{}")
    baseline_result = _write_text(reproduction_dir / "runs/ragtruth/baseline.json", "{}")
    diag_result = _write_text(reproduction_dir / "runs/diag150/results.json", "{}")
    external_table = _write_text(reproduction_dir / "table_1.md", "# External\n")

    manifest_path = reproduction_dir / "reproduction_manifest.json"
    manifest = {
        "commit": "fixture-commit",
        "generated_at": "2026-06-29T00:00:00Z",
        "quick": False,
        "result_scope": "pre_review_paper_candidate",
        "paper_run_candidate": True,
        "paper_result_eligible": False,
        "bootstrap_samples": 400,
        "bootstrap_seed": 20260612,
        "eligibility_gates": {
            "independent_diag150_review_complete": False,
            "independent_ragtruth_review_complete": False,
            "matched_external_baseline_available": True,
            "non_quick_run": True,
            "ragtruth_case_pack_available": True,
        },
        "inputs": {
            "experiment_spec": _file_record(experiment),
            "selected_ragtruth_case_pack": _file_record(selected),
            "candidate_predictions": [_file_record(candidate)],
        },
        "outputs": {
            "manifest": str(manifest_path),
            "machine_readable_tables": str(tables_path),
            "ablations": {
                "results": str(ablation_results_path),
                "matrix": str(ablation_matrix),
                "table": str(ablation_table),
            },
            "diag150": {"json": str(diag_result)},
            "ragtruth": {
                "json": str(ragtruth_result),
                "baseline_results_json": str(baseline_result),
            },
            "tables": {"external_results": str(external_table)},
        },
    }
    _write_json(manifest_path, manifest)
    return reproduction_dir, {"selected": selected}


def _file_record(path: Path) -> dict:
    return {
        "available": True,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
