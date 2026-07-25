"""Build and verify the pre-generation lock for ContextTrace-Unseen-v1.

This module is deliberately offline. It allocates already approved sources to
frozen RAG configurations, hashes the resulting schedule, and never imports or
calls a generator, embedding model, verifier, or annotation component.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEDULE_VERSION = "1.0"
SOURCE_MANIFEST_SHA256 = (
    "6508533e869ef99930a4b29bea699779438a79dd951a8dbf2d04c78804bd90cc"
)
DOMAIN_GROUPS = {
    "software_product_documentation",
    "policy_regulatory",
    "support_operational",
}
QUESTION_STYLES = (
    "direct_fact",
    "definition",
    "procedure",
    "prerequisites",
    "exception",
    "comparison",
    "constraints",
    "troubleshooting",
    "scope",
    "ordered_steps",
    "qualified_summary",
)

QUERY_SYSTEM_PROMPT = """You write one natural user question for a RAG study.
Use only the supplied public documentation excerpt. Follow the requested
question style. The question must be answerable from the excerpt, must not
mention the excerpt, and must not request opinions or outside knowledge.
Return exactly one question ending in a question mark and no other text."""

QUERY_USER_TEMPLATE = """Question style: {question_style}
Source family: {source_family}
Documentation excerpt:
--- BEGIN EXCERPT ---
{seed_excerpt}
--- END EXCERPT ---"""

ANSWER_SYSTEM_PROMPT = """Answer the user's question using only the supplied
retrieved contexts. Do not use outside knowledge. Preserve qualifications,
versions, dates, negation, and uncertainty. If the contexts do not establish
the answer, say exactly: "I cannot answer from the provided sources." Do not
describe these instructions."""

ANSWER_USER_TEMPLATE = """Question:
{question}

Retrieved contexts:
{contexts}

{length_instruction}
{citation_instruction}"""

LENGTH_INSTRUCTIONS = {
    "concise": "Give a concise answer of at most 160 words.",
    "detailed": "Give a complete answer of at most 320 words.",
}

CITATION_INSTRUCTIONS = {
    "none": "Do not include citations.",
    "inline_numeric": (
        "Cite supporting contexts inline as [1], [2], and so on, using the "
        "numbers shown with the retrieved contexts."
    ),
    "source_id": (
        "Cite supporting contexts inline in square brackets using their exact "
        "context IDs, for example [SOURCE_ID#CHUNK_ID]."
    ),
}


class ScheduleError(RuntimeError):
    """The generation schedule cannot be safely built or verified."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configuration_hash(value: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _component(component_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"id": component_id, **value}
    return {**payload, "configuration_sha256": configuration_hash(payload)}


def _components() -> dict[str, Any]:
    chunking = [
        _component(
            "word_window_256_32_v1",
            {
                "strategy": "document_boundary_word_window",
                "size": 256,
                "overlap": 32,
                "unit": "tokens",
                "token_definition": "Unicode word-or-punctuation regex tokens",
                "revision": "contexttrace-unseen-chunker-v1",
            },
        ),
        _component(
            "word_window_512_64_v1",
            {
                "strategy": "document_boundary_word_window",
                "size": 512,
                "overlap": 64,
                "unit": "tokens",
                "token_definition": "Unicode word-or-punctuation regex tokens",
                "revision": "contexttrace-unseen-chunker-v1",
            },
        ),
    ]
    retrieval = [
        _component(
            "bm25_okapi_v1",
            {
                "family": "bm25",
                "implementation": "ContextTrace offline BM25 Okapi",
                "revision": "contexttrace-unseen-retrieval-v1",
                "candidate_k": 20,
                "parameters": {"k1": 1.2, "b": 0.75},
                "tie_break": "ascending chunk_id",
            },
        ),
        _component(
            "minilm_cosine_exact_v1",
            {
                "family": "vector",
                "implementation": "SentenceTransformers normalized exact cosine",
                "revision": "contexttrace-unseen-retrieval-v1",
                "candidate_k": 20,
                "embedding_model": {
                    "model_id": "sentence-transformers/all-MiniLM-L6-v2",
                    "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                    "dimensions": 384,
                    "normalize_embeddings": True,
                    "sentence_transformers_version": "5.6.1",
                },
                "tie_break": "ascending chunk_id",
            },
        ),
        _component(
            "bm25_minilm_rrf_v1",
            {
                "family": "hybrid",
                "implementation": "BM25/vector reciprocal-rank fusion",
                "revision": "contexttrace-unseen-retrieval-v1",
                "candidate_k": 20,
                "constituents": ["bm25_okapi_v1", "minilm_cosine_exact_v1"],
                "parameters": {"rrf_k": 60, "lexical_weight": 1, "vector_weight": 1},
                "tie_break": "ascending chunk_id",
            },
        ),
    ]
    reranking = [
        _component(
            "disabled",
            {
                "enabled": False,
                "implementation": None,
                "revision": None,
                "candidate_input_k": 20,
            },
        ),
        _component(
            "query_likelihood_rerank_v1",
            {
                "enabled": True,
                "implementation": "deterministic BM25 query-likelihood reranker",
                "revision": "contexttrace-unseen-reranker-v1",
                "candidate_input_k": 20,
                "parameters": {"k1": 0.9, "b": 0.4, "exact_phrase_bonus": 0.15},
                "tie_break": "ascending pre-rerank rank, then chunk_id",
            },
        ),
    ]
    generators = [
        _component(
            "ollama_gemma3_4b_v1",
            {
                "provider": "Ollama",
                "endpoint": "/api/chat",
                "runtime_version": "0.32.1",
                "model": "gemma3:4b",
                "model_family": "Gemma 3",
                "manifest_digest": (
                    "sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a"
                ),
                "weight_digest": (
                    "sha256:aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25"
                ),
                "parameters": {
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9,
                    "seed_source": "case_seed",
                    "num_predict": 512,
                },
            },
        ),
        _component(
            "openai_gpt5_mini_20250807_v1",
            {
                "provider": "OpenAI",
                "endpoint": "/v1/responses",
                "model": "gpt-5-mini-2025-08-07",
                "model_family": "GPT-5 mini",
                "parameters": {
                    "store": False,
                    "reasoning": {"effort": "minimal"},
                    "text": {"verbosity": "low"},
                    "max_output_tokens": 800,
                    "tools": [],
                    "service_tier": "default",
                    "truncation": "disabled",
                    "random_seed": "unsupported_by_provider",
                },
            },
        ),
    ]
    prompts = []
    for length_id, length_instruction in LENGTH_INSTRUCTIONS.items():
        for citation_id, citation_instruction in CITATION_INSTRUCTIONS.items():
            prompt_id = f"rag_answer_{length_id}_{citation_id}_v1"
            prompts.append(
                _component(
                    prompt_id,
                    {
                        "system": ANSWER_SYSTEM_PROMPT,
                        "user_template": ANSWER_USER_TEMPLATE,
                        "length_instruction": length_instruction,
                        "citation_instruction": citation_instruction,
                        "citation_format": citation_id,
                    },
                )
            )
    return {
        "chunking": chunking,
        "retrieval": retrieval,
        "reranking": reranking,
        "generators": generators,
        "prompts": prompts,
        "query_authoring": _component(
            "gemma_query_author_v1",
            {
                "provider": "Ollama",
                "runtime_version": "0.32.1",
                "model": "gemma3:4b",
                "manifest_digest": (
                    "sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a"
                ),
                "weight_digest": (
                    "sha256:aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25"
                ),
                "system": QUERY_SYSTEM_PROMPT,
                "user_template": QUERY_USER_TEMPLATE,
                "seed_excerpt_strategy": (
                    "split at retained file markers; hash-order eligible sections; "
                    "select first section with 384-768 tokens"
                ),
                "parameters": {
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9,
                    "seed_source": "case_seed",
                    "num_predict": 128,
                },
                "validation": (
                    "one non-empty line, at most 240 characters, ending in '?'"
                ),
            },
        ),
    }


def _balanced_assignments(
    case_ids: Sequence[str], levels: Sequence[str], *, salt: str
) -> dict[str, str]:
    if len(case_ids) % len(levels):
        raise ScheduleError(f"{salt} cannot be balanced across {len(case_ids)} cases.")
    ordered = sorted(
        case_ids,
        key=lambda case_id: sha256_bytes(f"{salt}:{case_id}".encode("utf-8")),
    )
    repeats = len(case_ids) // len(levels)
    values = [level for level in levels for _ in range(repeats)]
    return dict(zip(ordered, values, strict=True))


def build_schedule(source_manifest: Mapping[str, Any]) -> dict[str, Any]:
    sources = list(source_manifest.get("sources", []))
    if len(sources) != 36:
        raise ScheduleError(f"Expected 36 acquired sources; found {len(sources)}.")
    families = [str(source["source_family"]) for source in sources]
    if len(set(families)) != 36:
        raise ScheduleError("Every acquired source must represent one unique family.")

    components = _components()
    cases: list[dict[str, Any]] = []
    sources_by_group: dict[str, list[Mapping[str, Any]]] = {
        group: [] for group in DOMAIN_GROUPS
    }
    for source in sources:
        group = str(source["domain_group"])
        if group not in sources_by_group:
            raise ScheduleError(f"Unexpected domain group: {group}")
        if source.get("source_conditions") != ["current", "canonical"]:
            raise ScheduleError(
                f"Natural source {source['source_id']} is not current and canonical."
            )
        sources_by_group[group].append(source)

    for group in sorted(DOMAIN_GROUPS):
        group_sources = sorted(
            sources_by_group[group], key=lambda source: str(source["source_family"])
        )
        if len(group_sources) != 12:
            raise ScheduleError(f"{group} must contain 12 source families.")
        group_case_ids = [
            f"ctu1_natural_{source['source_family']}_{slot:02d}"
            for source in group_sources
            for slot in range(1, 12)
        ]
        factors = {
            "retrieval": _balanced_assignments(
                group_case_ids,
                ["bm25_okapi_v1", "minilm_cosine_exact_v1", "bm25_minilm_rrf_v1"],
                salt=f"{group}:retrieval",
            ),
            "chunking": _balanced_assignments(
                group_case_ids,
                ["word_window_256_32_v1", "word_window_512_64_v1"],
                salt=f"{group}:chunking",
            ),
            "reranking": _balanced_assignments(
                group_case_ids,
                ["disabled", "query_likelihood_rerank_v1"],
                salt=f"{group}:reranking",
            ),
            "generator": _balanced_assignments(
                group_case_ids,
                ["ollama_gemma3_4b_v1", "openai_gpt5_mini_20250807_v1"],
                salt=f"{group}:generator",
            ),
            "citation": _balanced_assignments(
                group_case_ids,
                ["none", "inline_numeric", "source_id"],
                salt=f"{group}:citation",
            ),
            "context_count": _balanced_assignments(
                group_case_ids, ["3", "5", "8"], salt=f"{group}:context-count"
            ),
            "answer_length": _balanced_assignments(
                group_case_ids, ["concise", "detailed"], salt=f"{group}:answer-length"
            ),
        }
        for source in group_sources:
            for slot, question_style in enumerate(QUESTION_STYLES, start=1):
                case_id = f"ctu1_natural_{source['source_family']}_{slot:02d}"
                citation = factors["citation"][case_id]
                answer_length = factors["answer_length"][case_id]
                prompt_id = f"rag_answer_{answer_length}_{citation}_v1"
                seed = int(sha256_bytes(case_id.encode("utf-8"))[:8], 16)
                case = {
                    "case_id": case_id,
                    "track": "natural_ood",
                    "source_id": source["source_id"],
                    "source_family": source["source_family"],
                    "source_document_id": source["source_document_id"],
                    "domain_group": group,
                    "domain_id": source["domain_id"],
                    "publication_window": source["publication_window"],
                    "source_snapshot_sha256": source["snapshot_sha256"],
                    "query_plan": {
                        "authoring_configuration_id": "gemma_query_author_v1",
                        "question_style": question_style,
                        "seed": seed,
                        "human_selection_permitted": False,
                    },
                    "retrieval_configuration_id": factors["retrieval"][case_id],
                    "chunking_configuration_id": factors["chunking"][case_id],
                    "reranking_configuration_id": factors["reranking"][case_id],
                    "generator_configuration_id": factors["generator"][case_id],
                    "prompt_id": prompt_id,
                    "citation_format": citation,
                    "answer_length": answer_length,
                    "selected_context_count": int(factors["context_count"][case_id]),
                    "case_seed": seed,
                }
                cases.append(
                    {**case, "configuration_sha256": configuration_hash(case)}
                )

    schedule = {
        "schema_version": SCHEDULE_VERSION,
        "record_kind": "contexttrace_unseen_v1_generation_schedule",
        "status": "locked_pending_generation_authorization",
        "source_manifest": {
            "path": "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json",
            "sha256": SOURCE_MANIFEST_SHA256,
            "source_count": 36,
        },
        "scope": {
            "natural_ood": {
                "status": "scheduled",
                "planned_cases": 396,
                "cases_per_family": 11,
                "cases_per_domain_group": 132,
            },
            "temporal_source_condition": {
                "status": "blocked_missing_approved_source_pairs",
                "planned_cases": 100,
                "scheduled_cases": 0,
                "target_pair_types": {
                    "archived_policy_to_current_policy": 25,
                    "old_api_to_replacement_api": 25,
                    "noncanonical_to_canonical": 25,
                    "low_authority_to_authoritative": 25,
                },
                "rule": (
                    "No temporal slot may be created until two distinct, approved, "
                    "hash-pinned source snapshots and an independent authority basis "
                    "exist for its pair."
                ),
            },
        },
        "components": components,
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
                "required_next_decision": "approve_locked_natural_generation_schedule",
            },
            "pipeline_order": [
                "verify source and schedule hashes",
                "derive deterministic seed excerpt",
                "author one query with pinned local model",
                "chunk and index the complete source family",
                "retrieve candidates",
                "rerank when scheduled",
                "generate one unedited answer",
                "validate transport and trace structure",
                "retain eligible trace without semantic inspection",
            ],
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
                "allowed_source_privacy_classes": ["public", "public_pii_reviewed"],
                "forbidden_content": [
                    "personal data not explicitly reviewed",
                    "credentials",
                    "secrets",
                    "metadata_only source text",
                ],
                "logs_must_exclude": [
                    "authorization headers",
                    "API keys",
                    "account identifiers",
                    "local credential paths",
                ],
            },
            "hosted_cost_guard_usd": {
                "normal_operating_limit": 8.0,
                "contingency": 2.0,
                "hard_limit": 10.0,
                "scheduled_initial_requests": 198,
                "maximum_attempts_per_request": 2,
                "maximum_request_input_utf8_bytes": 50000,
                "maximum_output_tokens_per_attempt": 800,
                "conservative_all_attempts_upper_bound": 5.5836,
                "prices_per_million_tokens": {
                    "uncached_input": 0.25,
                    "cached_input": 0.025,
                    "output_and_reasoning": 2.0,
                },
                "preflight_input_estimate": (
                    "charge one token per UTF-8 input byte as a conservative upper bound"
                ),
                "preflight_oversize_action": "stop before request and record failure",
                "missing_usage_action": (
                    "charge the request's conservative preflight maximum"
                ),
                "limit_action": "stop before request; never change configuration",
                "pilot_and_retry_spend_included": True,
            },
            "eligibility": {
                "unedited_query_required": True,
                "unedited_answer_required": True,
                "manual_failure_injection_permitted": False,
                "verifier_calls_permitted": False,
                "labels_accessible": False,
                "semantic_selection_or_exclusion_permitted": False,
            },
        },
        "cases": sorted(cases, key=lambda case: str(case["case_id"])),
    }
    validate_schedule(schedule, source_manifest)
    return schedule


def _component_index(schedule: Mapping[str, Any], component_type: str) -> dict[str, Any]:
    values = schedule["components"][component_type]
    if not isinstance(values, list):
        raise ScheduleError(f"{component_type} must be a list.")
    result = {str(item["id"]): item for item in values}
    if len(result) != len(values):
        raise ScheduleError(f"{component_type} contains duplicate IDs.")
    for item in values:
        unhashed = {key: value for key, value in item.items() if key != "configuration_sha256"}
        if item.get("configuration_sha256") != configuration_hash(unhashed):
            raise ScheduleError(f"Invalid component hash: {item.get('id')}")
    return result


def validate_schedule(
    schedule: Mapping[str, Any], source_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    if schedule.get("schema_version") != SCHEDULE_VERSION:
        raise ScheduleError("Unexpected schedule schema version.")
    if schedule.get("status") != "locked_pending_generation_authorization":
        raise ScheduleError("Schedule is not in its pre-authorization state.")
    if schedule["source_manifest"]["sha256"] != SOURCE_MANIFEST_SHA256:
        raise ScheduleError("Schedule references the wrong source-manifest hash.")

    sources = {
        str(source["source_id"]): source for source in source_manifest.get("sources", [])
    }
    if len(sources) != 36:
        raise ScheduleError("Source manifest must contain 36 unique sources.")

    component_ids: dict[str, set[str]] = {}
    for component_type in (
        "chunking",
        "retrieval",
        "reranking",
        "generators",
        "prompts",
    ):
        component_ids[component_type] = set(
            _component_index(schedule, component_type)
        )
    query_authoring = schedule["components"]["query_authoring"]
    query_unhashed = {
        key: value
        for key, value in query_authoring.items()
        if key != "configuration_sha256"
    }
    if query_authoring["configuration_sha256"] != configuration_hash(query_unhashed):
        raise ScheduleError("Invalid query-authoring component hash.")

    cases = list(schedule.get("cases", []))
    if len(cases) != 396:
        raise ScheduleError(f"Natural schedule must contain 396 cases; found {len(cases)}.")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ScheduleError("Schedule contains duplicate case IDs.")

    family_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    group_factors: dict[str, dict[str, Counter[str]]] = {
        group: {
            "retrieval": Counter(),
            "chunking": Counter(),
            "reranking": Counter(),
            "generator": Counter(),
            "citation": Counter(),
            "context": Counter(),
            "answer_length": Counter(),
        }
        for group in DOMAIN_GROUPS
    }
    for case in cases:
        source = sources.get(str(case["source_id"]))
        if source is None:
            raise ScheduleError(f"Unknown source in {case['case_id']}.")
        for field in (
            "source_family",
            "source_document_id",
            "domain_group",
            "domain_id",
            "publication_window",
        ):
            if case[field] != source[field]:
                raise ScheduleError(f"{case['case_id']} has inconsistent {field}.")
        if case["source_snapshot_sha256"] != source["snapshot_sha256"]:
            raise ScheduleError(f"{case['case_id']} has the wrong source hash.")
        if case["track"] != "natural_ood":
            raise ScheduleError("Only Natural OOD cases may be scheduled at this gate.")
        if case["query_plan"].get("human_selection_permitted") is not False:
            raise ScheduleError(f"{case['case_id']} permits human query selection.")

        references = {
            "retrieval_configuration_id": "retrieval",
            "chunking_configuration_id": "chunking",
            "reranking_configuration_id": "reranking",
            "generator_configuration_id": "generators",
            "prompt_id": "prompts",
        }
        for field, component_type in references.items():
            if case[field] not in component_ids[component_type]:
                raise ScheduleError(f"{case['case_id']} references unknown {field}.")
        unhashed = {
            key: value for key, value in case.items() if key != "configuration_sha256"
        }
        if case.get("configuration_sha256") != configuration_hash(unhashed):
            raise ScheduleError(f"Invalid case hash: {case['case_id']}")

        family_counts[str(case["source_family"])] += 1
        group = str(case["domain_group"])
        group_counts[group] += 1
        factors = group_factors[group]
        factors["retrieval"][str(case["retrieval_configuration_id"])] += 1
        factors["chunking"][str(case["chunking_configuration_id"])] += 1
        factors["reranking"][str(case["reranking_configuration_id"])] += 1
        factors["generator"][str(case["generator_configuration_id"])] += 1
        factors["citation"][str(case["citation_format"])] += 1
        factors["context"][str(case["selected_context_count"])] += 1
        factors["answer_length"][str(case["answer_length"])] += 1

    if set(family_counts.values()) != {11} or len(family_counts) != 36:
        raise ScheduleError("Each of the 36 families must receive exactly 11 cases.")
    if group_counts != Counter({group: 132 for group in DOMAIN_GROUPS}):
        raise ScheduleError("Each domain group must receive exactly 132 cases.")
    expected_widths = {
        "retrieval": 3,
        "chunking": 2,
        "reranking": 2,
        "generator": 2,
        "citation": 3,
        "context": 3,
        "answer_length": 2,
    }
    for group, factors in group_factors.items():
        for factor, counts in factors.items():
            width = expected_widths[factor]
            if len(counts) != width or set(counts.values()) != {132 // width}:
                raise ScheduleError(
                    f"{group} has an unbalanced {factor} allocation: {dict(counts)}"
                )

    temporal = schedule["scope"]["temporal_source_condition"]
    if (
        temporal["status"] != "blocked_missing_approved_source_pairs"
        or temporal["scheduled_cases"] != 0
    ):
        raise ScheduleError("Temporal cases cannot be scheduled without approved pairs.")
    if schedule["execution_controls"]["authorization"]["model_calls_authorized"]:
        raise ScheduleError("The schedule builder cannot authorize model calls.")
    return {
        "status": "valid",
        "natural_cases": len(cases),
        "source_families": len(family_counts),
        "domain_group_counts": dict(sorted(group_counts.items())),
        "temporal_cases": 0,
        "model_calls_authorized": False,
    }


def _write_new_or_identical(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ScheduleError(f"Refusing to overwrite different frozen file: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def build_command(source_path: Path, output_path: Path) -> dict[str, Any]:
    if sha256_file(source_path) != SOURCE_MANIFEST_SHA256:
        raise ScheduleError("Candidate source manifest no longer matches its approved hash.")
    source_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    schedule = build_schedule(source_manifest)
    payload = (json.dumps(schedule, indent=2, sort_keys=True) + "\n").encode("utf-8")
    schedule_sha256 = sha256_bytes(payload)
    _write_new_or_identical(output_path, payload)
    sidecar = output_path.with_suffix(output_path.suffix + ".sha256")
    _write_new_or_identical(
        sidecar, f"{schedule_sha256}  {output_path.name}\n".encode("utf-8")
    )
    return {
        **validate_schedule(schedule, source_manifest),
        "schedule_sha256": schedule_sha256,
        "output": str(output_path),
        "sidecar": str(sidecar),
    }


def verify_command(
    source_path: Path, schedule_path: Path, expected_sha256: str | None
) -> dict[str, Any]:
    if sha256_file(source_path) != SOURCE_MANIFEST_SHA256:
        raise ScheduleError("Candidate source manifest no longer matches its approved hash.")
    actual_sha256 = sha256_file(schedule_path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ScheduleError(
            f"Schedule hash mismatch: expected {expected_sha256}, found {actual_sha256}."
        )
    source_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    return {
        **validate_schedule(schedule, source_manifest),
        "schedule_sha256": actual_sha256,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--source-manifest", type=Path, required=True)
        subparser.add_argument("--schedule", type=Path, required=True)
        if name == "verify":
            subparser.add_argument("--expected-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_command(args.source_manifest, args.schedule)
        else:
            result = verify_command(
                args.source_manifest, args.schedule, args.expected_sha256
            )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ScheduleError) as exc:
        print(f"generation schedule error: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
