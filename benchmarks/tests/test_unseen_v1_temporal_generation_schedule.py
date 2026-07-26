from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.build_temporal_generation_schedule import (
    TemporalScheduleError,
    build_command,
    build_schedule,
    configuration_hash,
    sha256_file,
    validate_schedule,
    verify_command,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks/contexttrace_unseen_v1"
CATALOG_PATH = BASE / "temporal_pre_acquisition_catalog.json"
MANIFEST_PATH = BASE / "temporal_source_manifest.json"
LEDGER_PATH = BASE / "temporal_acquisition_ledger.json"
VALIDATION_PATH = BASE / "temporal_acquisition_validation.json"
SCHEDULE_PATH = BASE / "temporal_generation_schedule.json"
NATURAL_SCHEDULE_PATH = BASE / "generation_schedule.json"


def _inputs() -> tuple[dict, dict, dict]:
    return (
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
        json.loads(VALIDATION_PATH.read_text(encoding="utf-8")),
    )


def _schedule() -> dict:
    return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))


def _rehash(case: dict) -> None:
    unhashed = {
        key: value for key, value in case.items() if key != "configuration_sha256"
    }
    case["configuration_sha256"] = configuration_hash(unhashed)


def test_temporal_schedule_is_deterministic_and_balanced() -> None:
    catalog, manifest, validation = _inputs()
    first = build_schedule(catalog, manifest, validation)
    second = build_schedule(catalog, manifest, validation)
    assert first == second == _schedule()
    result = validate_schedule(first, catalog, manifest, validation)
    assert result == {
        "status": "valid_pending_generation_authorization",
        "case_count": 100,
        "pair_count": 20,
        "pair_type_counts": {
            "archived_policy_to_current_policy": 25,
            "low_authority_to_authoritative": 25,
            "noncanonical_to_canonical": 25,
            "old_api_to_replacement_api": 25,
        },
        "context_mode_counts": {
            "left_only": 40,
            "mixed_left_first": 20,
            "mixed_right_first": 20,
            "right_only": 20,
        },
        "generator_counts": {
            "ollama_gemma3_4b_v1": 50,
            "openai_gpt5_mini_20250807_v1": 50,
        },
        "hosted_hard_limit_usd": 3.0,
        "conservative_all_attempts_upper_bound_usd": 1.41,
        "model_calls_authorized": False,
        "verifier_calls_authorized": False,
        "labels_accessible": False,
    }


def test_schedule_hash_and_sidecar_are_frozen() -> None:
    digest = sha256_file(SCHEDULE_PATH)
    assert digest == "b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d"
    assert SCHEDULE_PATH.with_suffix(".json.sha256").read_text(encoding="utf-8") == (
        f"{digest}  {SCHEDULE_PATH.name}\n"
    )


def test_temporal_components_are_golden_compatible_with_natural_track() -> None:
    temporal = _schedule()["components"]
    natural = json.loads(NATURAL_SCHEDULE_PATH.read_text(encoding="utf-8"))[
        "components"
    ]
    for kind in ("chunking", "retrieval", "reranking", "generators", "prompts"):
        assert temporal[kind] == natural[kind]
    assert temporal["question_planning"]["model_call_required"] is False


def test_style_context_rotation_removes_preliminary_confound() -> None:
    schedule = _schedule()
    by_style: dict[str, Counter[str]] = {}
    for case in schedule["cases"]:
        style = case["question_plan"]["question_style"]
        by_style.setdefault(style, Counter())[case["context_mode"]] += 1
    expected = Counter(
        {
            "left_only": 8,
            "mixed_left_first": 4,
            "mixed_right_first": 4,
            "right_only": 4,
        }
    )
    assert set(by_style) == {
        "direct_fact",
        "scope",
        "comparison",
        "constraints",
        "qualified_summary",
    }
    assert all(counts == expected for counts in by_style.values())
    assert schedule["design_amendment"]["source_or_case_substitution"] is False


def test_queries_are_frozen_unique_and_not_model_authored() -> None:
    cases = _schedule()["cases"]
    queries = [case["question_plan"]["query"] for case in cases]
    assert len(queries) == len(set(queries)) == 100
    assert all(query.endswith("?") and "\n" not in query for query in queries)
    assert all(len(query) <= 240 for query in queries)
    assert all(
        case["question_plan"]["human_selection_permitted"] is False
        and case["question_plan"]["model_call_required"] is False
        for case in cases
    )


def test_privacy_cost_and_authorization_boundaries_are_locked() -> None:
    controls = _schedule()["execution_controls"]
    assert controls["privacy"]["openai_store"] is False
    assert controls["privacy"]["allowed_source_privacy_classes"] == ["public"]
    assert controls["hosted_cost_guard_usd"]["hard_limit"] == 3.0
    assert (
        controls["hosted_cost_guard_usd"]["maximum_request_input_utf8_bytes"]
        == 50000
    )
    assert (
        controls["hosted_cost_guard_usd"]["conservative_all_attempts_upper_bound"]
        == 1.41
    )
    assert set(controls["authorization"].values()) >= {False}
    assert controls["eligibility"]["verifier_calls_permitted"] is False
    assert controls["eligibility"]["labels_accessible"] is False


def test_validator_rejects_candidate_source_pool_mutation() -> None:
    catalog, manifest, validation = _inputs()
    schedule = build_schedule(catalog, manifest, validation)
    case = next(
        item
        for item in schedule["cases"]
        if len(item["candidate_source_ids_in_tie_order"]) == 2
    )
    case["candidate_source_ids_in_tie_order"].reverse()
    _rehash(case)
    with pytest.raises(TemporalScheduleError, match="candidate source pool"):
        validate_schedule(schedule, catalog, manifest, validation)


def test_validator_rejects_query_mutation_even_when_case_is_rehashed() -> None:
    catalog, manifest, validation = _inputs()
    schedule = build_schedule(catalog, manifest, validation)
    case = schedule["cases"][0]
    case["question_plan"]["query"] = "A different question?"
    case["question_plan"]["query_sha256"] = configuration_hash(
        {"query": case["question_plan"]["query"]}
    )
    _rehash(case)
    with pytest.raises(TemporalScheduleError, match="frozen question"):
        validate_schedule(schedule, catalog, manifest, validation)


def test_validator_rejects_case_hash_mutation() -> None:
    catalog, manifest, validation = _inputs()
    schedule = build_schedule(catalog, manifest, validation)
    schedule["cases"][0]["selected_context_limit"] = 2
    with pytest.raises(TemporalScheduleError, match="answer contract|case hash"):
        validate_schedule(schedule, catalog, manifest, validation)


def test_validator_rejects_component_drift_even_when_component_is_rehashed() -> None:
    catalog, manifest, validation = _inputs()
    schedule = build_schedule(catalog, manifest, validation)
    component = schedule["components"]["retrieval"][0]
    component["candidate_k"] = 99
    unhashed = {
        key: value
        for key, value in component.items()
        if key != "configuration_sha256"
    }
    component["configuration_sha256"] = configuration_hash(unhashed)
    with pytest.raises(TemporalScheduleError, match="compatible components"):
        validate_schedule(schedule, catalog, manifest, validation)


def test_validator_rejects_downstream_authorization() -> None:
    catalog, manifest, validation = _inputs()
    schedule = build_schedule(catalog, manifest, validation)
    schedule["execution_controls"]["authorization"]["generation_authorized"] = True
    with pytest.raises(TemporalScheduleError, match="cannot authorize"):
        validate_schedule(schedule, catalog, manifest, validation)


def test_build_and_verify_are_hash_guarded(tmp_path: Path) -> None:
    output = tmp_path / "schedule.json"
    result = build_command(
        catalog_path=CATALOG_PATH,
        source_manifest_path=MANIFEST_PATH,
        acquisition_ledger_path=LEDGER_PATH,
        acquisition_validation_path=VALIDATION_PATH,
        output_path=output,
    )
    assert verify_command(
        catalog_path=CATALOG_PATH,
        source_manifest_path=MANIFEST_PATH,
        acquisition_ledger_path=LEDGER_PATH,
        acquisition_validation_path=VALIDATION_PATH,
        schedule_path=output,
        expected_sha256=result["schedule_sha256"],
    )["status"] == "valid_pending_generation_authorization"
    with pytest.raises(TemporalScheduleError, match="hash mismatch"):
        verify_command(
            catalog_path=CATALOG_PATH,
            source_manifest_path=MANIFEST_PATH,
            acquisition_ledger_path=LEDGER_PATH,
            acquisition_validation_path=VALIDATION_PATH,
            schedule_path=output,
            expected_sha256="0" * 64,
        )


def test_build_refuses_to_overwrite_different_schedule(tmp_path: Path) -> None:
    output = tmp_path / "schedule.json"
    kwargs = {
        "catalog_path": CATALOG_PATH,
        "source_manifest_path": MANIFEST_PATH,
        "acquisition_ledger_path": LEDGER_PATH,
        "acquisition_validation_path": VALIDATION_PATH,
        "output_path": output,
    }
    build_command(**kwargs)
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(TemporalScheduleError, match="Refusing to overwrite"):
        build_command(**kwargs)
