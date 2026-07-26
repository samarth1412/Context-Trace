"""Execute only the authorized ContextTrace-Unseen-v1 temporal schedule.

The collector imports the already-tested Natural OOD retrieval and transport
primitives, but has no query-authoring path. It accepts only the exact frozen
100-case schedule, retains answers unedited in a private directory, and never
imports or invokes ContextTrace verifier or NLI code.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx
import numpy as np
from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.contexttrace_unseen_v1 import collect_natural_ood as natural
from benchmarks.contexttrace_unseen_v1.acquire_temporal_sources import (
    validate_offline,
)
from benchmarks.contexttrace_unseen_v1.build_temporal_generation_schedule import (
    validate_schedule,
)


AUTHORIZED_SCHEDULE_SHA256 = (
    "b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d"
)
COLLECTION_PROTOCOL_VERSION = "contexttrace-unseen-temporal-v1"
TRACE_SCHEMA_VERSION = "candidate-trace-v1"
EXACT_OWNER_STATEMENT = (
    "I authorize execution of temporal generation schedule SHA-256 "
    "b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d "
    "under the recorded USD 3 hard ceiling. This authorizes only the 100 "
    "frozen answer-generation slots and permitted transport retries. It does "
    "not authorize source substitution, query editing, verifier or NLI calls, "
    "annotation, evaluation, publication, or release."
)


def verify_environment(
    schedule: Mapping[str, Any], *, require_hosted: bool
) -> dict[str, Any]:
    reference = schedule["execution_controls"]["reference_environment"]
    installed: dict[str, str] = {}
    for package, expected in natural.REQUIRED_PACKAGE_VERSIONS.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise natural.CollectionError(
                f"Pinned dependency is missing: {package}=={expected}"
            ) from exc
        if actual != expected:
            raise natural.CollectionError(
                f"Pinned dependency mismatch for {package}: "
                f"expected {expected}, got {actual}."
            )
        installed[package] = actual
    python_version = platform.python_version()
    if python_version != str(reference["python"]):
        raise natural.CollectionError(
            f"Pinned Python mismatch: expected {reference['python']}, "
            f"got {python_version}."
        )
    ollama = subprocess.run(
        ["ollama", "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if str(reference["ollama"]) not in ollama:
        raise natural.CollectionError(
            f"Pinned Ollama mismatch: expected {reference['ollama']}."
        )
    generators = natural.component_index(schedule, "generators")
    local = generators["ollama_gemma3_4b_v1"]
    manifest_path = (
        Path.home()
        / ".ollama/models/manifests/registry.ollama.ai/library/gemma3/4b"
    )
    expected_manifest = str(local["manifest_digest"]).split(":", 1)[1]
    if (
        not manifest_path.is_file()
        or natural.sha256_file(manifest_path) != expected_manifest
    ):
        raise natural.CollectionError(
            "Pinned Ollama Gemma manifest digest does not match."
        )
    modelfile = subprocess.run(
        ["ollama", "show", str(local["model"]), "--modelfile"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected_weight = str(local["weight_digest"]).replace(":", "-")
    if expected_weight not in modelfile:
        raise natural.CollectionError(
            "Pinned Ollama Gemma weight digest does not match."
        )
    if require_hosted and not os.environ.get("OPENAI_API_KEY"):
        raise natural.CollectionError(
            "OPENAI_API_KEY is absent; hosted generation cannot start."
        )
    return {
        "python": python_version,
        "platform": f"macOS-{platform.mac_ver()[0]}-{platform.machine()}",
        "packages": installed,
        "ollama": str(reference["ollama"]),
        "ollama_manifest_sha256": expected_manifest,
        "ollama_weight_sha256": expected_weight.removeprefix("sha256-"),
        "hosted_key_present": bool(os.environ.get("OPENAI_API_KEY")),
    }


def preflight(
    *,
    project_root: Path,
    acquisition_root: Path,
    collection_root: Path,
    authorized_schedule_sha256: str,
    require_hosted: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = project_root / "benchmarks/contexttrace_unseen_v1"
    schedule_path = base / "temporal_generation_schedule.json"
    source_path = base / "temporal_source_manifest.json"
    catalog_path = base / "temporal_pre_acquisition_catalog.json"
    ledger_path = base / "temporal_acquisition_ledger.json"
    validation_path = base / "temporal_acquisition_validation.json"
    authorization_path = base / "temporal_run_authorization.json"

    actual_schedule_hash = natural.sha256_file(schedule_path)
    if authorized_schedule_sha256 != AUTHORIZED_SCHEDULE_SHA256:
        raise natural.CollectionError(
            "CLI authorization hash is not the recorded authorization."
        )
    if actual_schedule_hash != authorized_schedule_sha256:
        raise natural.CollectionError(
            "Temporal schedule hash differs from the authorization."
        )
    sidecar_fields = schedule_path.with_suffix(".json.sha256").read_text(
        encoding="utf-8"
    ).split()
    if not sidecar_fields or sidecar_fields[0] != actual_schedule_hash:
        raise natural.CollectionError(
            "Temporal schedule hash sidecar differs from the schedule."
        )
    authorization = natural.load_json(authorization_path)
    if (
        authorization.get("authorized_schedule_sha256")
        != AUTHORIZED_SCHEDULE_SHA256
        or authorization.get("hard_ceiling_usd") != 3.0
        or authorization.get("project_owner_statement") != EXACT_OWNER_STATEMENT
        or authorization.get("authorized_scope")
        != {
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
    ):
        raise natural.CollectionError(
            "Recorded temporal generation authorization is absent or incomplete."
        )

    schedule = natural.load_json(schedule_path)
    sources = natural.load_json(source_path)
    catalog = natural.load_json(catalog_path)
    ledger = natural.load_json(ledger_path)
    acquisition_validation = natural.load_json(validation_path)
    validate_schedule(schedule, catalog, sources, acquisition_validation)
    acquisition = validate_offline(
        catalog=catalog,
        manifest=sources,
        ledger=ledger,
        workspace=acquisition_root,
        schema_path=base / "source_manifest.schema.json",
        calibration=natural.load_json(base / "calibration/registry.json"),
        natural=natural.load_json(base / "candidate_source_manifest.json"),
    )
    if (
        schedule["scope"] != {
            "track": "temporal_source_condition",
            "pairs": 20,
            "cases_per_pair": 5,
            "cases_per_pair_type": 25,
            "scheduled_cases": 100,
        }
        or len(schedule["cases"]) != 100
    ):
        raise natural.CollectionError("Authorized temporal scope is not exact.")
    controls = schedule["execution_controls"]
    if (
        controls["authorization"]["generation_authorized"]
        or controls["authorization"]["verifier_calls_authorized"]
        or controls["authorization"]["annotation_authorized"]
        or controls["eligibility"]["source_substitution_permitted"]
        or controls["eligibility"]["semantic_selection_or_exclusion_permitted"]
        or controls["hosted_cost_guard_usd"]["hard_limit"] != 3.0
    ):
        raise natural.CollectionError("Frozen downstream boundaries changed.")
    if any(
        case["question_plan"]["model_call_required"]
        or case["question_plan"]["human_selection_permitted"]
        or natural.sha256_bytes(
            str(case["question_plan"]["query"]).encode("utf-8")
        )
        != case["question_plan"]["query_sha256"]
        for case in schedule["cases"]
    ):
        raise natural.CollectionError("A frozen temporal query is not exact.")

    environment = verify_environment(schedule, require_hosted=require_hosted)
    collection_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(collection_root, 0o700)
    record = {
        "status": "valid",
        "checked_at": natural.utc_now(),
        "schedule_sha256": actual_schedule_hash,
        "authorization_sha256": natural.sha256_file(authorization_path),
        "case_count": 100,
        "answer_generation_slots": 100,
        "query_authoring_calls": 0,
        "source_validation": acquisition,
        "environment": environment,
        "verifier_or_nli_calls": 0,
        "labels_accessible": False,
        "publication_authorized": False,
    }
    natural.atomic_json(collection_root / "preflight.json", record)
    return schedule, sources, catalog, record


class TemporalCollectionRunner(natural.CollectionRunner):
    def __init__(
        self,
        *,
        schedule: Mapping[str, Any],
        sources: Mapping[str, Any],
        catalog: Mapping[str, Any],
        acquisition_root: Path,
        output_root: Path,
        transport: natural.TransportClient | None = None,
    ) -> None:
        self.schedule = schedule
        self.output_root = output_root
        self.acquisition_root = acquisition_root
        self.transport = transport or natural.TransportClient(
            schedule["execution_controls"]
        )
        self.source_index = {
            str(source["source_id"]): dict(source)
            for source in sources["sources"]
        }
        self.pair_index = {
            str(pair["pair_id"]): dict(pair) for pair in catalog["pairs"]
        }
        self.chunking = natural.component_index(schedule, "chunking")
        self.retrieval = natural.component_index(schedule, "retrieval")
        self.reranking = natural.component_index(schedule, "reranking")
        self.generators = natural.component_index(schedule, "generators")
        self.prompts = natural.component_index(schedule, "prompts")
        vector_component = next(
            value
            for value in self.retrieval.values()
            if value["family"] == "vector"
        )
        self.encoder = natural.DenseEncoder(vector_component)
        self.embedding_cache = natural.EmbeddingCache(
            output_root / "cache/embeddings", self.encoder
        )
        self.budget = natural.BudgetLedger(
            output_root / "budget_ledger.json",
            AUTHORIZED_SCHEDULE_SHA256,
            schedule["execution_controls"]["hosted_cost_guard_usd"],
        )
        self.documents: dict[str, list[natural.Document]] = {}
        self.chunks: dict[tuple[str, str], list[natural.Chunk]] = {}

    def load_state(self, case: Mapping[str, Any]) -> dict[str, Any]:
        path = self.state_path(str(case["case_id"]))
        if not path.is_file():
            return {
                "schema_version": "1.0",
                "case_id": case["case_id"],
                "configuration_sha256": case["configuration_sha256"],
                "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
                "status": "not_started",
                "query": case["question_plan"]["query"],
                "query_sha256": case["question_plan"]["query_sha256"],
                "attempts": [],
            }
        state = natural.load_json(path)
        if (
            state.get("configuration_sha256") != case["configuration_sha256"]
            or state.get("schedule_sha256") != AUTHORIZED_SCHEDULE_SHA256
            or state.get("query") != case["question_plan"]["query"]
            or state.get("query_sha256") != case["question_plan"]["query_sha256"]
        ):
            raise natural.CollectionError(
                f"Resume state mismatch for {case['case_id']}."
            )
        pending = [
            item for item in state["attempts"] if item["status"] == "reserved"
        ]
        if pending:
            raise natural.PendingAttemptError(
                f"Case {case['case_id']} has an unsettled provider attempt."
            )
        if any(item.get("stage") != "answer" for item in state["attempts"]):
            raise natural.CollectionError(
                f"Non-answer model attempt found for {case['case_id']}."
            )
        return state

    def _rankable_pool(
        self,
        case: Mapping[str, Any],
        chunking: Mapping[str, Any],
        retrieval: Mapping[str, Any],
    ) -> tuple[list[natural.Chunk], list[natural.Chunk], np.ndarray | None]:
        rankable: list[natural.Chunk] = []
        canonical: list[natural.Chunk] = []
        embedding_blocks: list[np.ndarray] = []
        for source_order, source_id in enumerate(
            case["candidate_source_ids_in_tie_order"]
        ):
            source = self.source_index[str(source_id)]
            chunks = self.source_chunks(source, chunking)
            canonical.extend(chunks)
            rankable.extend(
                natural.Chunk(
                    id=f"pool-{source_order:02d}/{chunk.id}",
                    text=chunk.text,
                    document_path=chunk.document_path,
                    chunk_index=chunk.chunk_index,
                )
                for chunk in chunks
            )
            if retrieval["family"] in {"vector", "hybrid"}:
                embedding_blocks.append(
                    self.embedding_cache.embeddings(
                        source=source, chunking=chunking, chunks=chunks
                    )
                )
        embeddings = (
            np.vstack(embedding_blocks) if embedding_blocks else None
        )
        if not rankable or len(rankable) != len(canonical):
            raise natural.CollectionError("Frozen temporal source pool is empty.")
        return rankable, canonical, embeddings

    def _record_structural_failure(
        self, state: dict[str, Any], *, stage: str, failure: Exception | str
    ) -> str:
        state.update(
            {
                "status": "collection_failure",
                "failed_stage": stage,
                "failure_type": (
                    type(failure).__name__
                    if isinstance(failure, Exception)
                    else str(failure)
                ),
                "failed_at": natural.utc_now(),
            }
        )
        self.save_state(state)
        return "failed"

    def collect_case(self, case: Mapping[str, Any]) -> str:
        case_id = str(case["case_id"])
        state = self.load_state(case)
        if state["status"] == "completed":
            return "resumed_completed"
        if state["status"] == "collection_failure":
            return "resumed_failure"
        query = str(case["question_plan"]["query"])
        if (
            state["query"] != query
            or natural.sha256_bytes(query.encode("utf-8"))
            != case["question_plan"]["query_sha256"]
        ):
            raise natural.CollectionError(f"Frozen query changed for {case_id}.")

        chunking = self.chunking[str(case["chunking_configuration_id"])]
        retrieval = self.retrieval[str(case["retrieval_configuration_id"])]
        reranking_component = self.reranking[
            str(case["reranking_configuration_id"])
        ]
        try:
            rankable, canonical, embeddings = self._rankable_pool(
                case, chunking, retrieval
            )
            candidate_indices = natural.retrieve(
                query,
                rankable,
                retrieval,
                embeddings=embeddings,
                encoder=self.encoder,
            )
            ranked_indices = natural.rerank(
                query, candidate_indices, rankable, reranking_component
            )
            retrieved_chunks = [canonical[index] for index in ranked_indices]
            selected = retrieved_chunks[: int(case["selected_context_limit"])]
            if len(selected) < int(case["minimum_context_count"]):
                return self._record_structural_failure(
                    state,
                    stage="retrieval_structure",
                    failure="insufficient_locked_contexts",
                )
        except Exception as exc:
            return self._record_structural_failure(
                state, stage="retrieval_structure", failure=exc
            )

        prompt = self.prompts[str(case["prompt_id"])]
        answer_user = prompt["user_template"].format(
            question=query,
            contexts=natural.format_contexts(selected),
            length_instruction=prompt["length_instruction"],
            citation_instruction=prompt["citation_instruction"],
        )
        generator = self.generators[
            str(case["generator_configuration_id"])
        ]
        try:
            if generator["provider"] == "Ollama":
                result = self._attempt_local(
                    case_id=case_id,
                    stage="answer",
                    payload=natural.ollama_payload(
                        generator,
                        system_prompt=prompt["system"],
                        user_prompt=answer_user,
                        seed=int(case["case_seed"]),
                    ),
                    state=state,
                )
            elif generator["provider"] == "OpenAI":
                result = self._attempt_openai(
                    case_id=case_id,
                    payload=natural.openai_payload(
                        generator,
                        system_prompt=prompt["system"],
                        user_prompt=answer_user,
                    ),
                    state=state,
                )
            else:
                raise natural.CollectionError(
                    f"Unsupported locked generator: {generator['provider']}"
                )
        except Exception as exc:
            return self._record_structural_failure(
                state, stage="answer_transport", failure=exc
            )

        trace = {
            "case_id": case_id,
            "track": "temporal_source_condition",
            "pair_id": case["pair_id"],
            "context_mode": case["context_mode"],
            "query": query,
            "answer": result.text,
            "retrieved_chunks": [
                {
                    "id": chunk.id,
                    "text": chunk.text,
                    "source_id": chunk.id.split("/", 1)[0],
                    "document_path": chunk.document_path,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in retrieved_chunks
            ],
            "selected_context_ids": [chunk.id for chunk in selected],
            "citations": natural.extract_citations(
                result.text,
                citation_format=str(case["citation_format"]),
                selected=selected,
            ),
        }
        trace_path = self.output_root / "traces" / f"{case_id}.json"
        natural.atomic_json(trace_path, trace)

        pair = self.pair_index[str(case["pair_id"])]
        left_id = str(case["source_roles"]["left"]["source_id"])
        right_id = str(case["source_roles"]["right"]["source_id"])
        pair_sources = [self.source_index[left_id], self.source_index[right_id]]
        primary = self.source_index[
            str(case["candidate_source_ids_in_tie_order"][0])
        ]
        rerank_enabled = bool(reranking_component["enabled"])
        manifest_case = {
            "case_id": case_id,
            "track": "temporal_source_condition",
            "split": "untouched_test_candidate",
            "source_ids": [left_id, right_id],
            "primary_source_id": primary["source_id"],
            "source_family": primary["source_family"],
            "source_document_id": primary["source_document_id"],
            "domain_group": primary["domain_group"],
            "domain_id": primary["domain_id"],
            "publication_window": primary["publication_window"],
            "source_url": primary["source_url"],
            "canonical_identifier": primary["canonical_identifier"],
            "source_snapshot_sha256": primary["snapshot_sha256"],
            "retrieval": {
                "family": retrieval["family"],
                "implementation": retrieval["implementation"],
                "revision": retrieval["revision"],
                "top_k": retrieval["candidate_k"],
                "configuration_sha256": retrieval["configuration_sha256"],
            },
            "chunking": {
                "strategy": chunking["strategy"],
                "size": chunking["size"],
                "overlap": chunking["overlap"],
                "unit": chunking["unit"],
                "configuration_sha256": chunking["configuration_sha256"],
            },
            "reranking": {
                "enabled": rerank_enabled,
                "implementation": reranking_component["implementation"],
                "revision": reranking_component["revision"],
                "top_n": len(selected) if rerank_enabled else None,
                "configuration_sha256": reranking_component[
                    "configuration_sha256"
                ],
            },
            "generator": {
                "provider": generator["provider"],
                "model": generator["model"],
                "model_family": generator["model_family"],
                "revision": generator.get(
                    "manifest_digest", generator["model"]
                ),
                "configuration_sha256": generator["configuration_sha256"],
            },
            "prompt_sha256": prompt["configuration_sha256"],
            "generation_parameters": generator["parameters"],
            "collection_timestamp": result.completed_at,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "license_access": {
                "license_ids": sorted(
                    {str(source["license"]["license_id"]) for source in pair_sources}
                ),
                "redistribution": "permitted",
            },
            "privacy_classification": "public",
            "origin": "natural_rag_run",
            "untouched_eligible": True,
            "labels_accessible_at_generation": False,
            "verifier_history": [],
            "trace_artifact_path": str(
                trace_path.relative_to(self.output_root)
            ),
            "trace_sha256": natural.sha256_file(trace_path),
            "retrieved_chunk_ids": [
                chunk.id for chunk in retrieved_chunks
            ],
            "selected_context_ids": [chunk.id for chunk in selected],
            "citation_format": case["citation_format"],
            "answer_length_chars": len(result.text),
            "context_count": len(selected),
            "generation_status": "completed",
            "configuration_sha256": case["configuration_sha256"],
            "source_condition_pair": {
                "pair_id": pair["pair_id"],
                "pair_type": pair["pair_type"],
                "left_source_id": left_id,
                "right_source_id": right_id,
                "authority_basis": pair["authority_basis"],
            },
            "metadata": {
                "answer_length": case["answer_length"],
                "question_style": case["question_plan"]["question_style"],
                "question_configuration_sha256": schedule_question_hash(
                    self.schedule
                ),
                "query_sha256": case["question_plan"]["query_sha256"],
                "case_seed": case["case_seed"],
                "context_mode": case["context_mode"],
                "candidate_source_ids_in_tie_order": case[
                    "candidate_source_ids_in_tie_order"
                ],
            },
        }
        state.update(
            {
                "status": "completed",
                "completed_at": result.completed_at,
                "trace_artifact": str(
                    trace_path.relative_to(self.output_root)
                ),
                "trace_sha256": natural.sha256_file(trace_path),
                "manifest_case": manifest_case,
            }
        )
        self.save_state(state)
        return "completed"

    def write_candidate_manifest(self) -> dict[str, Any]:
        completed: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for case in self.schedule["cases"]:
            path = self.state_path(str(case["case_id"]))
            if not path.is_file():
                continue
            state = natural.load_json(path)
            if state["status"] == "completed":
                completed.append(state["manifest_case"])
            elif state["status"] == "collection_failure":
                failures.append(
                    {
                        "case_id": state["case_id"],
                        "failed_stage": state["failed_stage"],
                        "failure_type": state["failure_type"],
                    }
                )
        manifest = {
            "schema_version": "1.0",
            "manifest_kind": "contexttrace_unseen_v1_cases",
            "created_at": natural.utc_now(),
            "collection_protocol_version": COLLECTION_PROTOCOL_VERSION,
            "claim_policy_version": "contexttrace-unseen-claim-policy-v1",
            "label_access": {
                "labels_created": False,
                "labels_accessible": False,
                "first_accessed_at": None,
                "custodian": None,
            },
            "cases": sorted(completed, key=lambda value: value["case_id"]),
        }
        natural.atomic_json(
            self.output_root / "candidate_case_manifest.json", manifest
        )
        summary = {
            "status": (
                "complete"
                if len(completed) + len(failures)
                == len(self.schedule["cases"])
                else "in_progress"
            ),
            "updated_at": natural.utc_now(),
            "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
            "scheduled_answer_slots": 100,
            "completed_cases": len(completed),
            "collection_failures": failures,
            "hosted_charged_cost_usd": self.budget.charged_total(),
            "hard_ceiling_usd": float(self.budget.guard["hard_limit"]),
            "query_authoring_calls": 0,
            "labels_created": False,
            "verifier_or_nli_calls": 0,
            "publication_authorized": False,
        }
        natural.atomic_json(
            self.output_root / "collection_summary.json", summary
        )
        return summary


def schedule_question_hash(schedule: Mapping[str, Any]) -> str:
    return str(
        schedule["components"]["question_planning"]["configuration_sha256"]
    )


def validate_collection(
    *,
    schedule: Mapping[str, Any],
    output_root: Path,
    schema_path: Path,
) -> dict[str, Any]:
    case_index = {
        str(case["case_id"]): case for case in schedule["cases"]
    }
    terminal = completed = 0
    failures: list[dict[str, str]] = []
    for case_id, case in case_index.items():
        state_path = output_root / "records" / f"{case_id}.json"
        if not state_path.is_file():
            raise natural.CollectionError(f"Missing case state: {case_id}.")
        state = natural.load_json(state_path)
        if (
            state.get("schedule_sha256") != AUTHORIZED_SCHEDULE_SHA256
            or state.get("configuration_sha256")
            != case["configuration_sha256"]
            or state.get("query") != case["question_plan"]["query"]
            or state.get("query_sha256")
            != case["question_plan"]["query_sha256"]
        ):
            raise natural.CollectionError(
                f"Frozen state mismatch for {case_id}."
            )
        attempts = state.get("attempts", [])
        if (
            any(
                item.get("stage") != "answer"
                or item.get("attempt_number") not in (1, 2)
                or item.get("status") == "reserved"
                for item in attempts
            )
            or len(attempts) > 2
        ):
            raise natural.CollectionError(
                f"Unauthorized or unsettled attempt for {case_id}."
            )
        expected_provider = (
            "Ollama"
            if case["generator_configuration_id"]
            == "ollama_gemma3_4b_v1"
            else "OpenAI"
        )
        if any(item.get("provider") != expected_provider for item in attempts):
            raise natural.CollectionError(
                f"Generator route mismatch for {case_id}."
            )
        if state["status"] == "completed":
            completed += 1
            manifest_case = state["manifest_case"]
            trace_path = output_root / str(state["trace_artifact"])
            if (
                not trace_path.is_file()
                or natural.sha256_file(trace_path) != state["trace_sha256"]
                or state["trace_sha256"] != manifest_case["trace_sha256"]
            ):
                raise natural.CollectionError(
                    f"Trace hash mismatch for {case_id}."
                )
            trace = natural.load_json(trace_path)
            allowed = set(case["candidate_source_ids_in_tie_order"])
            if (
                trace.get("query") != case["question_plan"]["query"]
                or trace.get("answer") == ""
                or any(
                    chunk.get("source_id") not in allowed
                    for chunk in trace.get("retrieved_chunks", [])
                )
                or not set(trace.get("selected_context_ids", []))
                <= {
                    str(chunk["id"])
                    for chunk in trace.get("retrieved_chunks", [])
                }
            ):
                raise natural.CollectionError(
                    f"Trace structure mismatch for {case_id}."
                )
            if (
                manifest_case.get("verifier_history") != []
                or manifest_case.get("labels_accessible_at_generation")
                is not False
                or manifest_case.get("source_ids")
                != [
                    case["source_roles"]["left"]["source_id"],
                    case["source_roles"]["right"]["source_id"],
                ]
            ):
                raise natural.CollectionError(
                    f"Downstream boundary mismatch for {case_id}."
                )
        elif state["status"] == "collection_failure":
            failures.append(
                {
                    "case_id": case_id,
                    "failed_stage": str(state["failed_stage"]),
                    "failure_type": str(state["failure_type"]),
                }
            )
        else:
            raise natural.CollectionError(
                f"Nonterminal case state: {case_id}."
            )
        terminal += 1

    manifest_path = output_root / "candidate_case_manifest.json"
    manifest = natural.load_json(manifest_path)
    schema = natural.load_json(schema_path)
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise natural.CollectionError(
            "Candidate case manifest schema failure: "
            + "; ".join(error.message for error in errors[:5])
        )
    if (
        len(manifest["cases"]) != completed
        or {case["case_id"] for case in manifest["cases"]}
        != {
            case_id
            for case_id in case_index
            if natural.load_json(
                output_root / "records" / f"{case_id}.json"
            )["status"]
            == "completed"
        }
    ):
        raise natural.CollectionError("Candidate manifest case set changed.")

    ledger = natural.load_json(output_root / "budget_ledger.json")
    if (
        ledger.get("schedule_sha256") != AUTHORIZED_SCHEDULE_SHA256
        or ledger.get("hard_limit_usd") != 3.0
        or any(
            attempt.get("status") == "reserved"
            for attempt in ledger.get("attempts", [])
        )
    ):
        raise natural.CollectionError("Hosted budget ledger is invalid.")
    charged = sum(
        float(attempt["charged_cost_usd"])
        for attempt in ledger.get("attempts", [])
    )
    if charged > 3.0:
        raise natural.CollectionError("Hosted hard ceiling was exceeded.")
    return {
        "status": "valid_unlabeled_temporal_collection",
        "validated_at": natural.utc_now(),
        "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
        "terminal_slots": terminal,
        "completed_cases": completed,
        "collection_failures": failures,
        "hosted_attempts": len(ledger.get("attempts", [])),
        "hosted_charged_cost_usd": charged,
        "query_authoring_calls": 0,
        "verifier_or_nli_calls": 0,
        "labels_created": False,
        "evaluation_performed": False,
    }


def freeze_private_unlabeled_manifest(
    *, output_root: Path, validation: Mapping[str, Any]
) -> dict[str, Any]:
    candidate_path = output_root / "candidate_case_manifest.json"
    preflight_path = output_root / "preflight.json"
    budget_path = output_root / "budget_ledger.json"
    frozen = {
        "schema_version": "1.0",
        "record_kind": (
            "contexttrace_unseen_v1_private_temporal_unlabeled_manifest"
        ),
        "frozen_at": natural.utc_now(),
        "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
        "candidate_case_manifest_sha256": natural.sha256_file(candidate_path),
        "preflight_sha256": natural.sha256_file(preflight_path),
        "budget_ledger_sha256": natural.sha256_file(budget_path),
        "validation": dict(validation),
        "labels_created": False,
        "labels_accessible": False,
        "verifier_or_nli_calls": 0,
        "publication_authorized": False,
    }
    path = output_root / "frozen/temporal_unlabeled_manifest.json"
    natural.atomic_json(path, frozen)
    digest = natural.sha256_file(path)
    sidecar = path.with_suffix(".json.sha256")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    temporary = sidecar.with_name(f".{sidecar.name}.tmp")
    temporary.write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    os.replace(temporary, sidecar)
    return {
        "path": str(path),
        "sha256": digest,
        "candidate_case_manifest_sha256": frozen[
            "candidate_case_manifest_sha256"
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preflight", "run", "validate"),
        help=(
            "preflight and validate make no model calls; run executes all 100 "
            "frozen answer slots and then performs structural validation"
        ),
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--acquisition-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-temporal-acquisition"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-temporal-collection"),
    )
    parser.add_argument(
        "--authorized-schedule-sha256",
        required=True,
        help="must exactly match the recorded project-owner authorization",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project_root = args.project_root.resolve()
        output_root = args.output_root.resolve()
        schedule, sources, catalog, record = preflight(
            project_root=project_root,
            acquisition_root=args.acquisition_root.resolve(),
            collection_root=output_root,
            authorized_schedule_sha256=args.authorized_schedule_sha256,
            require_hosted=args.command == "run",
        )
        if args.command == "preflight":
            print(json.dumps(record, indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            runner = TemporalCollectionRunner(
                schedule=schedule,
                sources=sources,
                catalog=catalog,
                acquisition_root=args.acquisition_root.resolve(),
                output_root=output_root,
            )
            summary = runner.run()
            if summary["status"] != "complete":
                raise natural.CollectionError(
                    "All 100 frozen slots are not terminal."
                )
        validation = validate_collection(
            schedule=schedule,
            output_root=output_root,
            schema_path=(
                project_root
                / "benchmarks/contexttrace_unseen_v1/case_manifest.schema.json"
            ),
        )
        frozen = freeze_private_unlabeled_manifest(
            output_root=output_root, validation=validation
        )
        natural.atomic_json(
            output_root / "collection_validation.json", validation
        )
        print(
            json.dumps(
                {"validation": validation, "frozen": frozen},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (
        natural.CollectionError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
        httpx.HTTPError,
    ) as exc:
        print(f"Temporal collection stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
