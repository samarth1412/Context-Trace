"""Collect typed Jev completeness signals using selected evidence only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

from benchmarks.external_fiveway_confirmation.ambiguity_gate import (
    GateError,
    _load_env,
    _nonnegative_int,
    _probability_map,
    _unit_float,
)
from benchmarks.jev_claim_verification.experiment import (
    LABEL_CRITERIA,
    VERDICT_INSTRUCTIONS,
    enforce_remote_policy,
)
from benchmarks.jev_v2_verification.run import load_case_pack, shared_input
from contexttrace.config import load_config
from contexttrace.verify.schema import TraceContext


FEATURES = {
    "every_requirement_supported": {
        "instructions": (
            "Does `selected_evidence` directly support every independently verifiable requirement "
            "in `claim`, rather than only its main topic or some of its assertions?"
        ),
        "true": "Every material assertion in the claim is directly supported.",
        "false": "At least one material assertion is absent, weaker, or unsupported.",
    },
    "no_material_omission": {
        "instructions": (
            "Would accepting `claim` from `selected_evidence` require filling in no missing material "
            "fact, condition, exception, attribution, or causal link?"
        ),
        "true": "No material fact or link must be supplied beyond the evidence.",
        "false": "Acceptance requires at least one material fact or link not stated in the evidence.",
    },
    "entity_relation_alignment": {
        "instructions": (
            "Do the entities, roles, relations, and attributions in `selected_evidence` exactly cover "
            "those asserted by `claim`?"
        ),
        "true": "The claim's entities, roles, relations, and attributions are all aligned.",
        "false": "At least one entity, role, relation, or attribution is missing or different.",
    },
    "qualifier_scope_alignment": {
        "instructions": (
            "Does `selected_evidence` support every qualifier and scope choice in `claim`, including "
            "universals, negation, modality, comparison, degree, and exceptions?"
        ),
        "true": "All applicable qualifiers and scope choices are supported or absent from the claim.",
        "false": "At least one qualifier or scope choice is stronger, missing, or different.",
    },
    "numeric_temporal_alignment": {
        "instructions": (
            "Does `selected_evidence` exactly support every number, quantity, date, duration, order, "
            "and temporal condition asserted by `claim`?"
        ),
        "true": "All applicable numeric and temporal details match or are absent from the claim.",
        "false": "At least one numeric or temporal detail is unsupported or mismatched.",
    },
    "coordination_coverage": {
        "instructions": (
            "When `claim` joins assertions with and, or, lists, relative clauses, or appositives, "
            "does `selected_evidence` support every material joined component?"
        ),
        "true": "Every material joined component is supported, or the claim has no such component.",
        "false": "Only some joined components are supported.",
    },
    "no_inference_gap": {
        "instructions": (
            "Can `claim` be accepted from `selected_evidence` without relying on outside knowledge, "
            "speculation, or a merely plausible inference?"
        ),
        "true": "The evidence directly establishes the claim without an outside inference gap.",
        "false": "The claim needs outside knowledge, speculation, or a merely plausible inference.",
    },
}
SUPPORT_EXTENT_CRITERIA = {
    "complete_support": (
        "Every material assertion, entity, relation, qualifier, number, date, attribution, and "
        "joined component in the claim is directly supported by the selected evidence."
    ),
    "partial_support": (
        "The evidence supports the claim's main topic or some assertions, but at least one material "
        "assertion or detail is absent, weaker, or requires an unsupported inference."
    ),
}
SUPPORT_EXTENT_INSTRUCTIONS = (
    "Choose whether `selected_evidence` completely supports `claim` or supports only part of it. "
    "Use only the supplied evidence. A claim is complete only when every material component is "
    "directly established."
)


def run_signals(
    cases: list[dict[str, Any]],
    *,
    client: object,
    choice_factory: object,
    noul_factory: object,
    noul_criteria_factory: object,
    model: str,
    checkpoint: str | Path | None = None,
    split_metadata: dict[str, Any] | None = None,
    selector: str = "shared_lexical",
    semantic_encoder: object | None = None,
) -> dict[str, Any]:
    rows = []
    for case in cases:
        contexts, input_audit = _selected_input(
            case,
            selector=selector,
            semantic_encoder=semantic_encoder,
        )
        state = {
            "claim": str(case["claim"]),
            "selected_evidence": [
                {"id": context.id, "text": context.text} for context in contexts
            ],
        }
        questions = {
            "verdict": choice_factory(  # type: ignore[operator]
                instructions=VERDICT_INSTRUCTIONS,
                criteria=LABEL_CRITERIA,
            ),
            "support_extent": choice_factory(  # type: ignore[operator]
                instructions=SUPPORT_EXTENT_INSTRUCTIONS,
                criteria=SUPPORT_EXTENT_CRITERIA,
            ),
        }
        for name, definition in FEATURES.items():
            questions["completeness_%s" % name] = noul_factory(  # type: ignore[operator]
                instructions=definition["instructions"],
                criteria=noul_criteria_factory(  # type: ignore[operator]
                    true=definition["true"], false=definition["false"]
                ),
            )
        started = time.perf_counter()
        response = client.system_one(state=state, questions=questions, model=model)  # type: ignore[attr-defined]
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping):
            raise GateError("TypeSafe completeness response omitted answers.")
        verdict_answer = answers.get("verdict")
        if verdict_answer is None:
            raise GateError("TypeSafe completeness response omitted verdict.")
        base_verdict = str(getattr(verdict_answer, "choice", "")).strip().casefold()
        probabilities = _probability_map(getattr(verdict_answer, "probabilities", None))
        if base_verdict not in LABEL_CRITERIA or set(probabilities) != set(LABEL_CRITERIA):
            raise GateError("TypeSafe returned an invalid five-way verdict distribution.")
        extent_answer = answers.get("support_extent")
        if extent_answer is None:
            raise GateError("TypeSafe completeness response omitted support extent.")
        extent_choice = str(getattr(extent_answer, "choice", "")).strip().casefold()
        extent_probabilities = _probability_map(
            getattr(extent_answer, "probabilities", None)
        )
        if (
            extent_choice not in SUPPORT_EXTENT_CRITERIA
            or set(extent_probabilities) != set(SUPPORT_EXTENT_CRITERIA)
        ):
            raise GateError("TypeSafe returned an invalid support-extent distribution.")
        feature_values = {}
        for name in FEATURES:
            answer = answers.get("completeness_%s" % name)
            if answer is None:
                raise GateError("TypeSafe completeness response omitted %s." % name)
            feature_values[name] = _unit_float(getattr(answer, "noul", None), name)
        usage = getattr(response, "usage", None)
        if usage is None:
            raise GateError("TypeSafe completeness response omitted usage.")
        state_json = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        rows.append(
            {
                "case_id": case["id"],
                "dataset": case["dataset"],
                "expected_verdict": case["expected_verdict"],
                "development_partition": case.get("development_partition"),
                "input_audit": {
                    **input_audit,
                    "remote_sent_fields": ["claim", "selected_evidence"],
                    "remote_state_sha256": hashlib.sha256(state_json.encode("utf-8")).hexdigest(),
                    "query_sent": False,
                    "evaluation_label_sent": False,
                    "selector": selector,
                },
                "signals": {
                    "base_verdict": base_verdict,
                    "base_probabilities": probabilities,
                    "base_confidence": _unit_float(
                        getattr(verdict_answer, "confidence", None), "verdict confidence"
                    ),
                    "support_extent_choice": extent_choice,
                    "support_extent_probabilities": extent_probabilities,
                    "support_extent_confidence": _unit_float(
                        getattr(extent_answer, "confidence", None),
                        "support extent confidence",
                    ),
                    "completeness_features": feature_values,
                },
                "request": {
                    "requested_model": model,
                    "resolved_model": str(getattr(response, "model", "")),
                    "latency_ms": latency_ms,
                    "usage": {
                        "input_tokens": _nonnegative_int(
                            getattr(usage, "input_tokens", None), "input_tokens"
                        ),
                        "output_tokens": _nonnegative_int(
                            getattr(usage, "output_tokens", None), "output_tokens"
                        ),
                    },
                    "generated_explanation": None,
                    "generated_evidence_spans": [],
                    "generated_matched_facts": [],
                },
            }
        )
        if checkpoint is not None:
            _write(Path(checkpoint), _result(rows, split_metadata or {}, model))
    return _result(rows, split_metadata or {}, model)


def _result(
    rows: list[dict[str, Any]], split_metadata: dict[str, Any], model: str
) -> dict[str, Any]:
    return {
        "schema_version": "jev-completeness-signals-2.0",
        "experiment": "contexttrace_jev_complete_support",
        "split": split_metadata,
        "requested_model": model,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "labels_sent_to_model": False,
        "generated_explanations": False,
        "cases_completed": len(rows),
        "rows": rows,
    }


def _selected_input(
    case: dict[str, Any],
    *,
    selector: str,
    semantic_encoder: object | None,
) -> tuple[list[TraceContext], dict[str, Any]]:
    if selector == "shared_lexical":
        return shared_input(case)
    if selector != "semantic_minilm" or semantic_encoder is None:
        raise GateError("semantic_minilm requires a local semantic encoder.")
    source = [
        TraceContext(id=str(item["id"]), text=str(item["text"]))
        for item in case["contexts"]
        if str(item.get("text") or "").strip()
    ]
    texts = [str(case["claim"]), *(context.text for context in source)]
    embeddings = semantic_encoder.encode(  # type: ignore[attr-defined]
        texts,
        batch_size=64,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    claim_embedding = embeddings[0]
    scored = sorted(
        (
            (float(embedding @ claim_embedding), index, context)
            for index, (context, embedding) in enumerate(
                zip(source, embeddings[1:], strict=True)
            )
        ),
        key=lambda item: (-item[0], item[1]),
    )
    contexts = [item[2] for item in scored[:8]]
    exact = {
        "query": str(case.get("query") or ""),
        "claim": str(case["claim"]),
        "selected_evidence": [
            {"id": context.id, "text": context.text} for context in contexts
        ],
    }
    encoded = json.dumps(exact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return contexts, {
        "input_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "evaluation_label_sent": False,
        "sent_fields": ["query", "claim", "selected_evidence"],
        "exact_shared_input": exact,
        "source_context_count": len(source),
        "selected_span_count": len(contexts),
        "selected_spans": [
            {
                "id": context.id,
                "text_sha256": hashlib.sha256(context.text.encode("utf-8")).hexdigest(),
                "characters": len(context.text),
            }
            for context in contexts
        ],
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-split", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--model", default="jev-latest")
    parser.add_argument(
        "--selector",
        choices=("shared_lexical", "semantic_minilm"),
        default="shared_lexical",
    )
    parser.add_argument("--encoder-path")
    args = parser.parse_args(argv)
    if args.env_file:
        _load_env(args.env_file)
    enforce_remote_policy(local_only=load_config().local_only, allow_remote=args.allow_remote)
    try:
        from typesafe_sdk import Choice, Noul, NoulCriteria, TypeSafeClient
    except ImportError as exc:
        raise GateError("typesafe-sdk is required for completeness signals.") from exc
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise GateError("TYPESAFE_API_KEY is not set.")
    metadata, cases = load_case_pack(args.cases, expected_split=args.expected_split)
    semantic_encoder = None
    if args.selector == "semantic_minilm":
        if not args.encoder_path:
            parser.error("--selector semantic_minilm requires --encoder-path")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise GateError("sentence-transformers is required for semantic selection.") from exc
        semantic_encoder = SentenceTransformer(args.encoder_path, device="cpu")
    client = TypeSafeClient(
        api_key=api_key,
        base_url=os.environ.get("TYPESAFE_ENDPOINT") or None,
        timeout=120.0,
    )
    try:
        result = run_signals(
            cases,
            client=client,
            choice_factory=Choice,
            noul_factory=Noul,
            noul_criteria_factory=NoulCriteria,
            model=args.model,
            checkpoint=args.output,
            split_metadata=metadata,
            selector=args.selector,
            semantic_encoder=semantic_encoder,
        )
    finally:
        client.close()
    _write(Path(args.output), result)
    print(json.dumps({"cases": len(result["rows"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
