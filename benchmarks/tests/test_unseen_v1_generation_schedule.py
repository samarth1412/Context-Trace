from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.build_generation_schedule import (
    SOURCE_MANIFEST_SHA256,
    ScheduleError,
    build_command,
    build_schedule,
    sha256_file,
    validate_schedule,
    verify_command,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST = ROOT / "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"


def _sources() -> dict:
    assert sha256_file(SOURCE_MANIFEST) == SOURCE_MANIFEST_SHA256
    return json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))


def test_schedule_is_deterministic_and_balanced() -> None:
    source_manifest = _sources()
    first = build_schedule(source_manifest)
    second = build_schedule(source_manifest)
    assert first == second
    result = validate_schedule(first, source_manifest)
    assert result == {
        "status": "valid",
        "natural_cases": 396,
        "source_families": 36,
        "domain_group_counts": {
            "policy_regulatory": 132,
            "software_product_documentation": 132,
            "support_operational": 132,
        },
        "temporal_cases": 0,
        "model_calls_authorized": False,
    }


def test_schedule_locks_privacy_budget_and_model_identities() -> None:
    schedule = build_schedule(_sources())
    controls = schedule["execution_controls"]
    assert controls["privacy"]["openai_project_retention_mode"] == "default"
    assert controls["privacy"]["openai_store"] is False
    assert controls["hosted_cost_guard_usd"]["hard_limit"] == 10.0
    assert (
        controls["hosted_cost_guard_usd"]["conservative_all_attempts_upper_bound"]
        == 5.5836
    )
    assert controls["authorization"]["model_calls_authorized"] is False

    generators = {
        generator["id"]: generator for generator in schedule["components"]["generators"]
    }
    assert (
        generators["openai_gpt5_mini_20250807_v1"]["model"]
        == "gpt-5-mini-2025-08-07"
    )
    assert (
        generators["ollama_gemma3_4b_v1"]["manifest_digest"]
        == "sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a"
    )


def test_schedule_records_temporal_pair_blocker() -> None:
    schedule = build_schedule(_sources())
    temporal = schedule["scope"]["temporal_source_condition"]
    assert temporal["status"] == "blocked_missing_approved_source_pairs"
    assert temporal["scheduled_cases"] == 0
    assert sum(temporal["target_pair_types"].values()) == 100


def test_schedule_rejects_case_hash_mutation() -> None:
    source_manifest = _sources()
    schedule = build_schedule(source_manifest)
    schedule["cases"][0]["selected_context_count"] = 99
    with pytest.raises(ScheduleError, match="Invalid case hash"):
        validate_schedule(schedule, source_manifest)


def test_schedule_rejects_unbalanced_allocation_even_with_rehashed_case() -> None:
    source_manifest = _sources()
    schedule = build_schedule(source_manifest)
    changed = schedule["cases"][0]
    original = changed["generator_configuration_id"]
    changed["generator_configuration_id"] = (
        "openai_gpt5_mini_20250807_v1"
        if original == "ollama_gemma3_4b_v1"
        else "ollama_gemma3_4b_v1"
    )
    from benchmarks.contexttrace_unseen_v1.build_generation_schedule import (
        configuration_hash,
    )

    unhashed = {
        key: value for key, value in changed.items() if key != "configuration_sha256"
    }
    changed["configuration_sha256"] = configuration_hash(unhashed)
    with pytest.raises(ScheduleError, match="unbalanced generator"):
        validate_schedule(schedule, source_manifest)


def test_schedule_rejects_model_call_authorization() -> None:
    source_manifest = _sources()
    schedule = build_schedule(source_manifest)
    schedule["execution_controls"]["authorization"]["model_calls_authorized"] = True
    with pytest.raises(ScheduleError, match="cannot authorize model calls"):
        validate_schedule(schedule, source_manifest)


def test_build_writes_hash_and_verify_checks_it(tmp_path: Path) -> None:
    output = tmp_path / "generation_schedule.json"
    built = build_command(SOURCE_MANIFEST, output)
    assert output.exists()
    assert output.with_suffix(".json.sha256").exists()
    assert verify_command(
        SOURCE_MANIFEST, output, built["schedule_sha256"]
    )["status"] == "valid"
    with pytest.raises(ScheduleError, match="hash mismatch"):
        verify_command(SOURCE_MANIFEST, output, "0" * 64)


def test_build_refuses_to_overwrite_a_different_lock(tmp_path: Path) -> None:
    output = tmp_path / "generation_schedule.json"
    build_command(SOURCE_MANIFEST, output)
    changed = copy.deepcopy(json.loads(output.read_text(encoding="utf-8")))
    changed["status"] = "changed"
    output.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ScheduleError, match="Refusing to overwrite"):
        build_command(SOURCE_MANIFEST, output)
