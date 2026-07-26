"""Build and verify the offline temporal/source-condition generation lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.build_generation_schedule import (
    _components as natural_components,
)
from benchmarks.contexttrace_unseen_v1.build_temporal_pre_acquisition_catalog import (
    PAIR_TYPES,
    validate_catalog,
)


SCHEDULE_VERSION = "1.0"
CATALOG_SHA256 = "a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678"
SOURCE_MANIFEST_SHA256 = (
    "6b3bbd4dff5ed7a2a80e26f87a7cf17a670be92083071526d33c2a3f60abf96e"
)
ACQUISITION_LEDGER_SHA256 = (
    "2bb77e35b7f9fad3a080bcb2b2986cc7090e622de0444ea6f7240740a5584ca1"
)
ACQUISITION_VALIDATION_SHA256 = (
    "6f01d38b1f8d985da9d701ba250af219c2ba2a18a6c19c08f2bbe5d77b2e8a10"
)
BASE_CONTEXT_MODES = (
    "left_only",
    "left_only",
    "mixed_left_first",
    "right_only",
    "mixed_right_first",
)
QUESTION_TEMPLATES = {
    "direct_fact": "What does the available source material state about {topic}?",
    "scope": (
        "What is the scope of {topic}, including the entities, versions, or "
        "situations it covers?"
    ),
    "comparison": (
        "How do the available source versions or source types differ regarding "
        "{topic}?"
    ),
    "constraints": (
        "What requirements, limitations, exceptions, or replacement rules apply "
        "to {topic}?"
    ),
    "qualified_summary": (
        "What qualified summary of {topic} is supported, including any date, "
        "version, or source-authority limitations?"
    ),
}
PAIR_TOPICS = {
    "ctu1_pair_api_matplotlib_hist_density": (
        "Matplotlib histogram normalization through the deprecated normed "
        "parameter and its density replacement"
    ),
    "ctu1_pair_api_pillow_resampling_lanczos": (
        "Pillow image resampling after removal of Image.ANTIALIAS and use of "
        "LANCZOS or Resampling.LANCZOS"
    ),
    "ctu1_pair_api_pytest_yield_fixture": (
        "pytest's deprecated yield_fixture alias and the fixture replacement"
    ),
    "ctu1_pair_api_scipy_imageio_imread": (
        "image reading after deprecation of scipy.misc.imread and the ImageIO "
        "imread replacement"
    ),
    "ctu1_pair_api_sklearn_feature_names": (
        "scikit-learn feature-name access through get_feature_names and "
        "get_feature_names_out"
    ),
    "ctu1_pair_archived_coppa": (
        "Children's Online Privacy Protection requirements in 16 CFR part 312"
    ),
    "ctu1_pair_archived_hazardous_waste": (
        "hazardous-waste identification and listing under 40 CFR part 261"
    ),
    "ctu1_pair_archived_information_blocking": (
        "health-information-blocking requirements under 45 CFR part 171"
    ),
    "ctu1_pair_archived_transport_airworthiness": (
        "transport-aircraft airworthiness standards under 14 CFR part 25"
    ),
    "ctu1_pair_archived_workplace_safety": (
        "general-industry workplace-safety requirements under 29 CFR part 1910"
    ),
    "ctu1_pair_low_authority_cfaa_summary": (
        "the Computer Fraud and Abuse Act and 18 U.S.C. § 1030"
    ),
    "ctu1_pair_low_authority_coppa_summary": (
        "the Children's Online Privacy Protection Act and 15 U.S.C. §§ 6501–6506"
    ),
    "ctu1_pair_low_authority_dmca_summary": (
        "the Digital Millennium Copyright Act and 17 U.S.C. §§ 512 and 1201"
    ),
    "ctu1_pair_low_authority_hipaa": (
        "HIPAA administrative-simplification provisions in 42 U.S.C. "
        "§§ 1320d–1320d-9"
    ),
    "ctu1_pair_low_authority_osha_act_summary": (
        "the Occupational Safety and Health Act and 29 U.S.C. §§ 651–678"
    ),
    "ctu1_pair_noncanonical_civil_rights_action": (
        "the civil-rights cause of action in 42 U.S.C. § 1983"
    ),
    "ctu1_pair_noncanonical_copyright_fair_use": (
        "copyright fair use under 17 U.S.C. § 107"
    ),
    "ctu1_pair_noncanonical_foia_section": (
        "the Freedom of Information Act provisions in 5 U.S.C. § 552"
    ),
    "ctu1_pair_noncanonical_minimum_wage": (
        "federal minimum-wage provisions in 29 U.S.C. § 206"
    ),
    "ctu1_pair_noncanonical_patent_eligibility": (
        "patent-eligible subject matter under 35 U.S.C. § 101"
    ),
}


class TemporalScheduleError(RuntimeError):
    """The temporal generation schedule is invalid or unsafe."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configuration_hash(value: Mapping[str, Any] | Sequence[Any]) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def component(component_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"id": component_id, **value}
    return {**payload, "configuration_sha256": configuration_hash(payload)}


def components() -> dict[str, Any]:
    values = natural_components()
    values.pop("query_authoring")
    values["question_planning"] = component(
        "deterministic_temporal_questions_v1",
        {
            "implementation": "frozen pair-topic question templates",
            "revision": "contexttrace-unseen-temporal-question-plan-v1",
            "templates": QUESTION_TEMPLATES,
            "topics": PAIR_TOPICS,
            "human_authoring_after_lock_permitted": False,
            "model_call_required": False,
            "validation": (
                "one non-empty line, at most 240 characters, ending in '?'"
            ),
        },
    )
    return values


def answer_length_assignments(
    preliminary_cases: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for route in ("local", "hosted"):
        ids = sorted(
            (
                str(case["case_id"])
                for case in preliminary_cases
                if case["generator_route"] == route
            ),
            key=lambda case_id: sha256_bytes(
                f"temporal-answer-length:{route}:{case_id}".encode()
            ),
        )
        if len(ids) != 50:
            raise TemporalScheduleError(f"Expected 50 {route} cases.")
        for index, case_id in enumerate(ids):
            assignments[case_id] = "concise" if index < 25 else "detailed"
    return assignments


def rotated_context_modes(
    pairs: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    styles = tuple(QUESTION_TEMPLATES)
    for pair_type in PAIR_TYPES:
        group = sorted(
            (pair for pair in pairs if pair["pair_type"] == pair_type),
            key=lambda pair: str(pair["pair_id"]),
        )
        if len(group) != 5:
            raise TemporalScheduleError(f"{pair_type} must contain five pairs.")
        for rotation, pair in enumerate(group):
            for slot, style in enumerate(styles):
                result[(str(pair["pair_id"]), style)] = BASE_CONTEXT_MODES[
                    (slot + rotation) % len(BASE_CONTEXT_MODES)
                ]
    return result


def query_for(pair_id: str, question_style: str) -> str:
    try:
        query = QUESTION_TEMPLATES[question_style].format(topic=PAIR_TOPICS[pair_id])
    except KeyError as exc:
        raise TemporalScheduleError(
            f"Question plan is absent for {pair_id}/{question_style}."
        ) from exc
    if "\n" in query or len(query) > 240 or not query.endswith("?"):
        raise TemporalScheduleError(f"Invalid frozen query for {pair_id}.")
    return query


def candidate_sources(pair: Mapping[str, Any], context_mode: str) -> list[str]:
    left = str(pair["left_source_id"])
    right = str(pair["right_source_id"])
    return {
        "left_only": [left],
        "right_only": [right],
        "mixed_left_first": [left, right],
        "mixed_right_first": [right, left],
    }[context_mode]


def build_schedule(
    catalog: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    acquisition_validation: Mapping[str, Any],
) -> dict[str, Any]:
    validate_catalog(catalog)
    if (
        acquisition_validation.get("status") != "valid"
        or acquisition_validation.get("result", {}).get("source_count") != 37
        or acquisition_validation.get("result", {}).get("pair_count") != 20
    ):
        raise TemporalScheduleError("Temporal acquisition validation is not complete.")
    sources = {
        str(source["source_id"]): source
        for source in source_manifest.get("sources", [])
    }
    if len(sources) != 37:
        raise TemporalScheduleError("Temporal source manifest must contain 37 sources.")
    pairs = list(catalog["pairs"])
    pair_index = {str(pair["pair_id"]): pair for pair in pairs}
    preliminary_cases = list(catalog["case_plan"])
    preliminary_index = {
        str(case["case_id"]): case for case in preliminary_cases
    }
    if len(preliminary_index) != 100:
        raise TemporalScheduleError("Preliminary case plan must contain 100 cases.")
    context_modes = rotated_context_modes(pairs)
    lengths = answer_length_assignments(preliminary_cases)
    component_values = components()
    retrieval_ids = {
        "bm25": "bm25_okapi_v1",
        "vector": "minilm_cosine_exact_v1",
        "hybrid": "bm25_minilm_rrf_v1",
    }
    generator_ids = {
        "local": "ollama_gemma3_4b_v1",
        "hosted": "openai_gpt5_mini_20250807_v1",
    }
    cases: list[dict[str, Any]] = []
    for preliminary in sorted(
        preliminary_cases, key=lambda case: str(case["case_id"])
    ):
        case_id = str(preliminary["case_id"])
        pair = pair_index[str(preliminary["pair_id"])]
        style = str(preliminary["question_style"])
        mode = context_modes[(str(pair["pair_id"]), style)]
        query = query_for(str(pair["pair_id"]), style)
        candidate_ids = candidate_sources(pair, mode)
        length = lengths[case_id]
        citation = str(preliminary["citation_format"])
        source_roles: dict[str, Any] = {}
        for role, source_id, condition_field in (
            ("left", str(pair["left_source_id"]), "left_condition"),
            ("right", str(pair["right_source_id"]), "right_condition"),
        ):
            source = sources[source_id]
            source_roles[role] = {
                "source_id": source_id,
                "source_document_id": source["source_document_id"],
                "source_family": source["source_family"],
                "condition": pair[condition_field],
                "publication_window": source["publication_window"],
                "snapshot_sha256": source["snapshot_sha256"],
                "normalized_content_sha256": source[
                    "normalized_content_sha256"
                ],
            }
        seed = int(sha256_bytes(case_id.encode())[:8], 16)
        unhashed = {
            "case_id": case_id,
            "track": "temporal_source_condition",
            "pair_id": pair["pair_id"],
            "pair_type": pair["pair_type"],
            "pair_configuration_sha256": configuration_hash(pair),
            "domain_group": pair["domain_group"],
            "domain_id": pair["domain_id"],
            "source_roles": source_roles,
            "context_mode": mode,
            "candidate_source_ids_in_tie_order": candidate_ids,
            "require_context_from_each_candidate_source": False,
            "question_plan": {
                "configuration_id": "deterministic_temporal_questions_v1",
                "question_style": style,
                "topic": PAIR_TOPICS[str(pair["pair_id"])],
                "query": query,
                "query_sha256": sha256_bytes(query.encode("utf-8")),
                "human_selection_permitted": False,
                "model_call_required": False,
            },
            "retrieval_configuration_id": retrieval_ids[
                str(preliminary["retrieval_family"])
            ],
            "chunking_configuration_id": (
                f"word_window_{preliminary['chunk_size']}_"
                f"{preliminary['chunk_overlap']}_v1"
            ),
            "reranking_configuration_id": (
                "query_likelihood_rerank_v1"
                if preliminary["reranking_enabled"]
                else "disabled"
            ),
            "generator_configuration_id": generator_ids[
                str(preliminary["generator_route"])
            ],
            "prompt_id": f"rag_answer_{length}_{citation}_v1",
            "citation_format": citation,
            "answer_length": length,
            "selected_context_limit": 3,
            "minimum_context_count": 1,
            "case_seed": seed,
        }
        cases.append(
            {**unhashed, "configuration_sha256": configuration_hash(unhashed)}
        )
    schedule = {
        "schema_version": SCHEDULE_VERSION,
        "record_kind": "contexttrace_unseen_v1_temporal_generation_schedule",
        "status": "locked_pending_generation_authorization",
        "inputs": {
            "pre_acquisition_catalog": {
                "path": (
                    "benchmarks/contexttrace_unseen_v1/"
                    "temporal_pre_acquisition_catalog.json"
                ),
                "sha256": CATALOG_SHA256,
            },
            "temporal_source_manifest": {
                "path": (
                    "benchmarks/contexttrace_unseen_v1/"
                    "temporal_source_manifest.json"
                ),
                "sha256": SOURCE_MANIFEST_SHA256,
                "source_count": 37,
            },
            "acquisition_ledger_sha256": ACQUISITION_LEDGER_SHA256,
            "acquisition_validation_sha256": ACQUISITION_VALIDATION_SHA256,
        },
        "design_amendment": {
            "id": "temporal_style_context_deconfounding_v1",
            "preliminary_case_plan_sha256": configuration_hash(preliminary_cases),
            "changed_field": "context_mode only",
            "source_or_case_substitution": False,
            "reason": (
                "rotate the approved 2/1/1/1 context-mode multiset across the "
                "five pairs in each pair type so question style is not perfectly "
                "confounded with source availability"
            ),
            "rotation_rule": (
                "sort pairs within pair_type; rotate "
                "[left_only,left_only,mixed_left_first,right_only,"
                "mixed_right_first] by pair index 0..4"
            ),
            "model_or_verifier_results_inspected": False,
            "labels_accessible": False,
        },
        "scope": {
            "track": "temporal_source_condition",
            "scheduled_cases": 100,
            "pairs": 20,
            "cases_per_pair": 5,
            "cases_per_pair_type": 25,
        },
        "components": component_values,
        "execution_controls": {
            "reference_environment": {
                "python": "3.14.6",
                "platform": "macOS-26.5.2-arm64",
                "ollama": "0.32.1",
                "httpx": "0.28.1",
                "numpy": "2.5.0",
                "sentence_transformers": "5.6.1",
                "transformers": "5.14.1",
                "torch": "2.13.0",
                "environment_rule": (
                    "record exact installed versions and hashes before the first "
                    "run; any difference requires a pre-run lock amendment"
                ),
            },
            "authorization": {
                "model_calls_authorized": False,
                "generation_authorized": False,
                "verifier_calls_authorized": False,
                "annotation_authorized": False,
                "required_next_decision": (
                    "approve_exact_temporal_generation_schedule_hash"
                ),
            },
            "pipeline_order": [
                "verify catalog, source, acquisition, and schedule hashes",
                "load only the case's frozen candidate source side or sides",
                "chunk each candidate source independently",
                "use the exact frozen query without model authoring",
                "retrieve candidates across the allowed source pool",
                "rerank when scheduled",
                "select up to three contexts with stable tie ordering",
                "generate one unedited answer",
                "validate transport and trace structure",
                "retain without semantic inspection",
            ],
            "source_pool_rule": {
                "left_only": "only the pair's left source is indexed",
                "right_only": "only the pair's right source is indexed",
                "mixed_left_first": (
                    "both sources are indexed; left precedes right only for "
                    "stable chunk-ID and exact-score tie resolution"
                ),
                "mixed_right_first": (
                    "both sources are indexed; right precedes left only for "
                    "stable chunk-ID and exact-score tie resolution"
                ),
                "mixed_side_quota": None,
                "retrieval_may_naturally_select_one_or_both_sides": True,
            },
            "retry_policy": {
                "maximum_attempts": 2,
                "retry_only": [
                    "connection timeout",
                    "HTTP 408",
                    "HTTP 429",
                    "HTTP 500",
                    "HTTP 502",
                    "HTTP 503",
                    "HTTP 504",
                    "empty transport response",
                ],
                "backoff_seconds": [2],
                "jitter": False,
                "semantic_or_answer_quality_retry": False,
                "exhausted_action": "record collection failure; do not replace",
            },
            "timeouts_seconds": {
                "hosted_connect": 10,
                "hosted_read": 120,
                "local_connect": 10,
                "local_read": 180,
            },
            "concurrency": {"hosted": 1, "local": 1, "per_case": 1},
            "privacy": {
                "openai_project_retention_mode": "default",
                "openai_abuse_monitoring_retention_days_max": 30,
                "openai_store": False,
                "allowed_source_privacy_classes": ["public"],
                "forbidden_content": [
                    "personal data not explicitly reviewed",
                    "credentials",
                    "secrets",
                    "metadata-only source text",
                    "Wikimedia usernames or edit summaries",
                ],
                "logs_must_exclude": [
                    "authorization headers",
                    "API keys",
                    "account identifiers",
                    "local credential paths",
                ],
            },
            "hosted_cost_guard_usd": {
                "normal_operating_limit": 2.0,
                "contingency": 1.0,
                "hard_limit": 3.0,
                "scheduled_initial_requests": 50,
                "maximum_attempts_per_request": 2,
                "maximum_request_input_utf8_bytes": 50000,
                "maximum_output_tokens_per_attempt": 800,
                "conservative_all_attempts_upper_bound": 1.41,
                "prices_per_million_tokens": {
                    "uncached_input": 0.25,
                    "cached_input": 0.025,
                    "output_and_reasoning": 2.0,
                },
                "preflight_input_estimate": (
                    "charge one token per UTF-8 input byte as a conservative "
                    "upper bound"
                ),
                "preflight_oversize_action": (
                    "record structural failure before request; do not truncate "
                    "or substitute"
                ),
                "missing_usage_action": (
                    "charge the request's conservative preflight maximum"
                ),
                "limit_action": "stop before request; never change configuration",
                "pilot_and_retry_spend_included": True,
            },
            "eligibility": {
                "exact_frozen_query_required": True,
                "unedited_answer_required": True,
                "manual_failure_injection_permitted": False,
                "verifier_calls_permitted": False,
                "labels_accessible": False,
                "semantic_selection_or_exclusion_permitted": False,
                "source_substitution_permitted": False,
            },
        },
        "cases": cases,
    }
    validate_schedule(schedule, catalog, source_manifest, acquisition_validation)
    return schedule


def component_ids(schedule: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for kind in ("chunking", "retrieval", "reranking", "generators", "prompts"):
        values = schedule["components"][kind]
        ids = {str(value["id"]) for value in values}
        if len(ids) != len(values):
            raise TemporalScheduleError(f"Duplicate {kind} component.")
        for value in values:
            unhashed = {
                key: item
                for key, item in value.items()
                if key != "configuration_sha256"
            }
            if value["configuration_sha256"] != configuration_hash(unhashed):
                raise TemporalScheduleError(f"Invalid component hash: {value['id']}")
        result[kind] = ids
    plan = schedule["components"]["question_planning"]
    unhashed = {
        key: value for key, value in plan.items() if key != "configuration_sha256"
    }
    if plan["configuration_sha256"] != configuration_hash(unhashed):
        raise TemporalScheduleError("Invalid question-planning component hash.")
    return result


def validate_schedule(
    schedule: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    acquisition_validation: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        schedule.get("schema_version") != SCHEDULE_VERSION
        or schedule.get("record_kind")
        != "contexttrace_unseen_v1_temporal_generation_schedule"
        or schedule.get("status") != "locked_pending_generation_authorization"
    ):
        raise TemporalScheduleError("Unexpected temporal schedule identity or state.")
    expected_inputs = {
        "pre_acquisition_catalog": {
            "path": (
                "benchmarks/contexttrace_unseen_v1/"
                "temporal_pre_acquisition_catalog.json"
            ),
            "sha256": CATALOG_SHA256,
        },
        "temporal_source_manifest": {
            "path": (
                "benchmarks/contexttrace_unseen_v1/temporal_source_manifest.json"
            ),
            "sha256": SOURCE_MANIFEST_SHA256,
            "source_count": 37,
        },
        "acquisition_ledger_sha256": ACQUISITION_LEDGER_SHA256,
        "acquisition_validation_sha256": ACQUISITION_VALIDATION_SHA256,
    }
    if schedule.get("inputs") != expected_inputs:
        raise TemporalScheduleError("Schedule input hashes changed.")
    if acquisition_validation.get("status") != "valid":
        raise TemporalScheduleError("Acquisition validation is not valid.")
    if schedule.get("components") != components():
        raise TemporalScheduleError(
            "Temporal components differ from the frozen compatible components."
        )
    amendment = schedule.get("design_amendment") or {}
    if (
        amendment.get("id") != "temporal_style_context_deconfounding_v1"
        or amendment.get("preliminary_case_plan_sha256")
        != configuration_hash(catalog["case_plan"])
        or amendment.get("changed_field") != "context_mode only"
        or amendment.get("source_or_case_substitution") is not False
        or amendment.get("model_or_verifier_results_inspected") is not False
        or amendment.get("labels_accessible") is not False
    ):
        raise TemporalScheduleError("The deconfounding amendment changed.")
    ids = component_ids(schedule)
    sources = {
        str(source["source_id"]): source
        for source in source_manifest.get("sources", [])
    }
    pairs = {str(pair["pair_id"]): pair for pair in catalog["pairs"]}
    preliminary = {
        str(case["case_id"]): case for case in catalog["case_plan"]
    }
    expected_modes = rotated_context_modes(list(pairs.values()))
    expected_lengths = answer_length_assignments(list(preliminary.values()))
    cases = list(schedule.get("cases", []))
    if len(cases) != 100 or len({case["case_id"] for case in cases}) != 100:
        raise TemporalScheduleError("Temporal schedule must contain 100 unique cases.")
    counts: dict[str, Counter[str]] = {
        key: Counter()
        for key in (
            "pair",
            "pair_type",
            "question_style",
            "context_mode",
            "retrieval",
            "chunking",
            "reranking",
            "generator",
            "citation",
            "answer_length",
        )
    }
    style_modes: dict[str, Counter[str]] = {
        style: Counter() for style in QUESTION_TEMPLATES
    }
    generator_lengths: Counter[tuple[str, str]] = Counter()
    references = {
        "retrieval_configuration_id": "retrieval",
        "chunking_configuration_id": "chunking",
        "reranking_configuration_id": "reranking",
        "generator_configuration_id": "generators",
        "prompt_id": "prompts",
    }
    for case in cases:
        case_id = str(case["case_id"])
        planned = preliminary.get(case_id)
        pair = pairs.get(str(case["pair_id"]))
        if planned is None or pair is None:
            raise TemporalScheduleError(f"Unknown case or pair: {case_id}")
        if (
            case["track"] != "temporal_source_condition"
            or case["pair_type"] != pair["pair_type"]
            or case["pair_configuration_sha256"] != configuration_hash(pair)
            or case["domain_group"] != pair["domain_group"]
            or case["domain_id"] != pair["domain_id"]
            or case["require_context_from_each_candidate_source"] is not False
            or case["case_seed"]
            != int(sha256_bytes(case_id.encode("utf-8"))[:8], 16)
        ):
            raise TemporalScheduleError(f"{case_id} pair type changed.")
        for field, kind in references.items():
            if case[field] not in ids[kind]:
                raise TemporalScheduleError(f"{case_id} references unknown {field}.")
        style = str(planned["question_style"])
        expected_mode = expected_modes[(str(pair["pair_id"]), style)]
        if case["context_mode"] != expected_mode:
            raise TemporalScheduleError(f"{case_id} context rotation changed.")
        if case["candidate_source_ids_in_tie_order"] != candidate_sources(
            pair, expected_mode
        ):
            raise TemporalScheduleError(f"{case_id} candidate source pool changed.")
        expected_query = query_for(str(pair["pair_id"]), style)
        question = case["question_plan"]
        if (
            question["configuration_id"]
            != "deterministic_temporal_questions_v1"
            or question["topic"] != PAIR_TOPICS[str(pair["pair_id"])]
            or
            question["question_style"] != style
            or question["query"] != expected_query
            or question["query_sha256"] != sha256_bytes(expected_query.encode())
            or question["human_selection_permitted"] is not False
            or question["model_call_required"] is not False
        ):
            raise TemporalScheduleError(f"{case_id} frozen question changed.")
        for role, source_id, condition_field in (
            ("left", str(pair["left_source_id"]), "left_condition"),
            ("right", str(pair["right_source_id"]), "right_condition"),
        ):
            source = sources.get(source_id)
            record = case["source_roles"].get(role)
            if source is None or record is None:
                raise TemporalScheduleError(f"{case_id} source role is absent.")
            expected = {
                "source_id": source_id,
                "source_document_id": source["source_document_id"],
                "source_family": source["source_family"],
                "condition": pair[condition_field],
                "publication_window": source["publication_window"],
                "snapshot_sha256": source["snapshot_sha256"],
                "normalized_content_sha256": source[
                    "normalized_content_sha256"
                ],
            }
            if record != expected:
                raise TemporalScheduleError(f"{case_id} source role changed.")
        expected_retrieval = {
            "bm25": "bm25_okapi_v1",
            "vector": "minilm_cosine_exact_v1",
            "hybrid": "bm25_minilm_rrf_v1",
        }[str(planned["retrieval_family"])]
        if case["retrieval_configuration_id"] != expected_retrieval:
            raise TemporalScheduleError(f"{case_id} retrieval changed.")
        expected_chunk = (
            f"word_window_{planned['chunk_size']}_{planned['chunk_overlap']}_v1"
        )
        if case["chunking_configuration_id"] != expected_chunk:
            raise TemporalScheduleError(f"{case_id} chunking changed.")
        expected_rerank = (
            "query_likelihood_rerank_v1"
            if planned["reranking_enabled"]
            else "disabled"
        )
        if case["reranking_configuration_id"] != expected_rerank:
            raise TemporalScheduleError(f"{case_id} reranking changed.")
        expected_generator = {
            "local": "ollama_gemma3_4b_v1",
            "hosted": "openai_gpt5_mini_20250807_v1",
        }[str(planned["generator_route"])]
        if case["generator_configuration_id"] != expected_generator:
            raise TemporalScheduleError(f"{case_id} generator changed.")
        length = expected_lengths[case_id]
        if (
            case["answer_length"] != length
            or case["citation_format"] != planned["citation_format"]
            or case["prompt_id"]
            != f"rag_answer_{length}_{planned['citation_format']}_v1"
            or case["selected_context_limit"] != 3
            or case["minimum_context_count"] != 1
        ):
            raise TemporalScheduleError(f"{case_id} answer contract changed.")
        unhashed = {
            key: value
            for key, value in case.items()
            if key != "configuration_sha256"
        }
        if case["configuration_sha256"] != configuration_hash(unhashed):
            raise TemporalScheduleError(f"Invalid case hash: {case_id}")
        counts["pair"][str(pair["pair_id"])] += 1
        counts["pair_type"][str(pair["pair_type"])] += 1
        counts["question_style"][style] += 1
        counts["context_mode"][expected_mode] += 1
        counts["retrieval"][str(case["retrieval_configuration_id"])] += 1
        counts["chunking"][str(case["chunking_configuration_id"])] += 1
        counts["reranking"][str(case["reranking_configuration_id"])] += 1
        counts["generator"][expected_generator] += 1
        counts["citation"][str(case["citation_format"])] += 1
        counts["answer_length"][length] += 1
        style_modes[style][expected_mode] += 1
        generator_lengths[(expected_generator, length)] += 1
    expected_counts = {
        "pair": {5},
        "pair_type": {25},
        "question_style": {20},
        "context_mode": {40, 20},
        "retrieval": {34, 33},
        "chunking": {50},
        "reranking": {50},
        "generator": {50},
        "citation": {34, 33},
        "answer_length": {50},
    }
    for factor, allowed in expected_counts.items():
        if set(counts[factor].values()) != allowed:
            raise TemporalScheduleError(
                f"Unbalanced {factor}: {dict(counts[factor])}"
            )
    expected_style_mode = Counter(
        {
            "left_only": 8,
            "mixed_left_first": 4,
            "right_only": 4,
            "mixed_right_first": 4,
        }
    )
    if any(value != expected_style_mode for value in style_modes.values()):
        raise TemporalScheduleError("Question style remains confounded with context mode.")
    if set(generator_lengths.values()) != {25} or len(generator_lengths) != 4:
        raise TemporalScheduleError("Answer length is confounded with generator route.")
    controls = schedule["execution_controls"]
    authorization = controls["authorization"]
    if any(
        authorization[field]
        for field in (
            "model_calls_authorized",
            "generation_authorized",
            "verifier_calls_authorized",
            "annotation_authorized",
        )
    ):
        raise TemporalScheduleError("The schedule cannot authorize downstream work.")
    budget = controls["hosted_cost_guard_usd"]
    if (
        budget["scheduled_initial_requests"] != 50
        or budget["hard_limit"] != 3.0
        or budget["conservative_all_attempts_upper_bound"] != 1.41
        or budget["conservative_all_attempts_upper_bound"] > budget["hard_limit"]
    ):
        raise TemporalScheduleError("Hosted budget guard changed.")
    return {
        "status": "valid_pending_generation_authorization",
        "case_count": 100,
        "pair_count": 20,
        "pair_type_counts": dict(sorted(counts["pair_type"].items())),
        "context_mode_counts": dict(sorted(counts["context_mode"].items())),
        "generator_counts": dict(sorted(counts["generator"].items())),
        "hosted_hard_limit_usd": 3.0,
        "conservative_all_attempts_upper_bound_usd": 1.41,
        "model_calls_authorized": False,
        "verifier_calls_authorized": False,
        "labels_accessible": False,
    }


def write_new_or_identical(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise TemporalScheduleError(
                f"Refusing to overwrite a different frozen file: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def build_command(
    *,
    catalog_path: Path,
    source_manifest_path: Path,
    acquisition_ledger_path: Path,
    acquisition_validation_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    expected = {
        catalog_path: CATALOG_SHA256,
        source_manifest_path: SOURCE_MANIFEST_SHA256,
        acquisition_ledger_path: ACQUISITION_LEDGER_SHA256,
        acquisition_validation_path: ACQUISITION_VALIDATION_SHA256,
    }
    for path, digest in expected.items():
        if sha256_file(path) != digest:
            raise TemporalScheduleError(f"Input hash changed: {path}")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(acquisition_validation_path.read_text(encoding="utf-8"))
    schedule = build_schedule(catalog, manifest, validation)
    payload = (
        json.dumps(schedule, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    digest = sha256_bytes(payload)
    write_new_or_identical(output_path, payload)
    sidecar = output_path.with_suffix(output_path.suffix + ".sha256")
    write_new_or_identical(
        sidecar, f"{digest}  {output_path.name}\n".encode("utf-8")
    )
    return {
        **validate_schedule(schedule, catalog, manifest, validation),
        "schedule_sha256": digest,
        "output": str(output_path),
    }


def verify_command(
    *,
    catalog_path: Path,
    source_manifest_path: Path,
    acquisition_ledger_path: Path,
    acquisition_validation_path: Path,
    schedule_path: Path,
    expected_sha256: str | None,
) -> dict[str, Any]:
    for path, digest in (
        (catalog_path, CATALOG_SHA256),
        (source_manifest_path, SOURCE_MANIFEST_SHA256),
        (acquisition_ledger_path, ACQUISITION_LEDGER_SHA256),
        (acquisition_validation_path, ACQUISITION_VALIDATION_SHA256),
    ):
        if sha256_file(path) != digest:
            raise TemporalScheduleError(f"Input hash changed: {path}")
    actual = sha256_file(schedule_path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise TemporalScheduleError(
            f"Schedule hash mismatch: expected {expected_sha256}, found {actual}."
        )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(acquisition_validation_path.read_text(encoding="utf-8"))
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    return {
        **validate_schedule(schedule, catalog, manifest, validation),
        "schedule_sha256": actual,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    subparsers = value.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument(
            "--catalog",
            type=Path,
            default=Path(
                "benchmarks/contexttrace_unseen_v1/"
                "temporal_pre_acquisition_catalog.json"
            ),
        )
        subparser.add_argument(
            "--source-manifest",
            type=Path,
            default=Path(
                "benchmarks/contexttrace_unseen_v1/temporal_source_manifest.json"
            ),
        )
        subparser.add_argument(
            "--acquisition-ledger",
            type=Path,
            default=Path(
                "benchmarks/contexttrace_unseen_v1/"
                "temporal_acquisition_ledger.json"
            ),
        )
        subparser.add_argument(
            "--acquisition-validation",
            type=Path,
            default=Path(
                "benchmarks/contexttrace_unseen_v1/"
                "temporal_acquisition_validation.json"
            ),
        )
        subparser.add_argument(
            "--schedule",
            type=Path,
            default=Path(
                "benchmarks/contexttrace_unseen_v1/"
                "temporal_generation_schedule.json"
            ),
        )
        if name == "verify":
            subparser.add_argument("--expected-sha256")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    kwargs = {
        "catalog_path": args.catalog,
        "source_manifest_path": args.source_manifest,
        "acquisition_ledger_path": args.acquisition_ledger,
        "acquisition_validation_path": args.acquisition_validation,
    }
    try:
        if args.command == "build":
            result = build_command(**kwargs, output_path=args.schedule)
        else:
            result = verify_command(
                **kwargs,
                schedule_path=args.schedule,
                expected_sha256=args.expected_sha256,
            )
    except (OSError, ValueError, TemporalScheduleError) as exc:
        print(f"temporal schedule failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
