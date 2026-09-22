from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable, Mapping, Protocol

from contexttrace.config import load_config
from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.judges import (
    ALLOWED_VERDICTS,
    CONTRADICTED,
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNSUPPORTED,
    UNVERIFIABLE,
    JudgeVerdict,
)
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.verdicts import classify_claim


LABELS = (
    SUPPORTED,
    PARTIALLY_SUPPORTED,
    UNSUPPORTED,
    CONTRADICTED,
    UNVERIFIABLE,
)

LABEL_CRITERIA: dict[str, str] = {
    SUPPORTED: "The selected evidence directly entails every material part of the claim.",
    PARTIALLY_SUPPORTED: "The selected evidence supports some material parts of the claim, while other material parts are missing.",
    UNSUPPORTED: "The selected evidence is related to the claim but does not support what the claim asserts.",
    CONTRADICTED: "The selected evidence conflicts with the claim, including a wrong entity, date, number, negation, causal direction, or attribution.",
    UNVERIFIABLE: "The selected evidence is too ambiguous to decide whether the claim is supported or contradicted.",
}

VERDICT_INSTRUCTIONS = (
    "Classify how the selected evidence relates to the claim. Judge only from the selected "
    "evidence. Do not use outside knowledge or infer facts from evidence that was not supplied."
)


class JevExperimentError(RuntimeError):
    """Raised when the isolated Jev experiment cannot run safely."""


class SystemOneClient(Protocol):
    def system_one(self, *, state: object, questions: Mapping[str, object], model: str) -> object:
        """Evaluate typed System One questions."""


@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    split: str
    category: str
    query: str
    claim: str
    contexts: tuple[TraceContext, ...]
    expected_verdict: str


@dataclass(frozen=True)
class SelectedEvidence:
    contexts: tuple[TraceContext, ...]
    audit: tuple[dict[str, object], ...]


class ExperimentalJevJudge:
    """Experiment-only ClaimJudge backed by TypeSafe System One Choice.

    This class deliberately does not enter ContextTrace's production provider registry.
    Jev returns a typed classification and probabilities, so explanation and fact fields
    remain empty instead of being synthesized.
    """

    provider = "typesafe_jev"

    def __init__(
        self,
        *,
        client: SystemOneClient,
        choice_factory: Callable[..., object],
        model: str = "jev-latest",
    ) -> None:
        self.client = client
        self.choice_factory = choice_factory
        self.requested_model = model

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        state = build_jev_state(query=query, claim=claim, contexts=contexts)
        questions = {
            "verdict": self.choice_factory(
                instructions=VERDICT_INSTRUCTIONS,
                criteria=LABEL_CRITERIA,
            )
        }
        started = perf_counter()
        response = self.client.system_one(
            state=state,
            questions=questions,
            model=self.requested_model,
        )
        latency_ms = round((perf_counter() - started) * 1000.0, 3)

        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping) or "verdict" not in answers:
            raise JevExperimentError("TypeSafe response did not contain answers['verdict'].")
        answer = answers["verdict"]
        verdict = str(getattr(answer, "choice", "")).strip().lower()
        if verdict not in ALLOWED_VERDICTS:
            raise JevExperimentError("TypeSafe returned an unknown verdict: %r." % verdict)

        probabilities = _probability_map(getattr(answer, "probabilities", None))
        missing = [label for label in LABELS if label not in probabilities]
        if missing:
            raise JevExperimentError(
                "TypeSafe response omitted verdict probabilities: %s." % ", ".join(missing)
            )
        confidence = _unit_float(getattr(answer, "confidence", None), field="confidence")
        resolved_model = str(getattr(response, "model", "") or "").strip()
        if not resolved_model:
            raise JevExperimentError("TypeSafe response did not identify the resolved model version.")
        usage = getattr(response, "usage", None)
        if usage is None:
            raise JevExperimentError("TypeSafe response did not include token usage.")
        usage_payload = {
            "input_tokens": _optional_nonnegative_int(getattr(usage, "input_tokens", None)),
            "output_tokens": _optional_nonnegative_int(getattr(usage, "output_tokens", None)),
        }
        if usage_payload["input_tokens"] is None or usage_payload["output_tokens"] is None:
            raise JevExperimentError("TypeSafe response token usage was incomplete.")
        usage_payload["total_tokens"] = (
            usage_payload["input_tokens"] + usage_payload["output_tokens"]
        )

        return JudgeVerdict(
            verdict=verdict,
            confidence=confidence,
            reason="",
            matched_facts=[],
            missing_facts=[],
            conflicting_facts=[],
            provider=self.provider,
            model=resolved_model,
            raw={
                "probabilities": probabilities,
                "requested_model": self.requested_model,
                "resolved_model": resolved_model,
                "latency_ms": latency_ms,
                "usage": usage_payload,
            },
        )


def build_jev_state(
    *,
    query: str,
    claim: str,
    contexts: Iterable[TraceContext],
) -> dict[str, object]:
    """Build the complete remote payload from selected evidence only."""

    return {
        "query": str(query),
        "claim": str(claim),
        "selected_evidence": [
            {"id": context.id, "text": context.text}
            for context in contexts
        ],
    }


def select_evidence(case: ExperimentCase, *, mode: str = "semantic") -> SelectedEvidence:
    """Use ContextTrace's existing selector and retain only its selected spans."""

    match = find_best_evidence(case.claim, case.contexts, mode=mode, localize_spans=True)
    spans = list(match.supporting_spans or [])
    if not spans:
        fallback = match.span_dict()
        if fallback and match.score > 0:
            spans = [fallback]

    contexts: list[TraceContext] = []
    audit: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, span in enumerate(spans):
        source_id = str(span.get("context_id") or "")
        text = str(span.get("text") or "").strip()
        if not source_id or not text:
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        dedupe_key = (source_id, digest)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        selected_id = "%s:span:%s" % (source_id, index + 1)
        contexts.append(TraceContext(id=selected_id, text=text))
        audit.append(
            {
                "selected_id": selected_id,
                "source_context_id": source_id,
                "sha256": digest,
                "characters": len(text),
            }
        )
    return SelectedEvidence(contexts=tuple(contexts), audit=tuple(audit))


def baseline_assessment(
    case: ExperimentCase,
    selected: SelectedEvidence,
    *,
    mode: str = "semantic",
) -> dict[str, object]:
    """Run the stable classifier against exactly the evidence sent to Jev."""

    match = find_best_evidence(
        case.claim,
        selected.contexts,
        mode=mode,
        localize_spans=False,
    )
    result = classify_claim(
        Claim(id=case.case_id, text=case.claim),
        match,
        has_contexts=bool(selected.contexts),
        mode=mode,
    )
    return {
        "provider": "contexttrace_stable",
        "verdict": result.verdict,
        "confidence": result.confidence,
    }


def run_experiment(
    cases: Iterable[ExperimentCase],
    *,
    judge: ExperimentalJevJudge | None,
    mode: str = "semantic",
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for case in cases:
        selected = select_evidence(case, mode=mode)
        state = build_jev_state(query=case.query, claim=case.claim, contexts=selected.contexts)
        state_json = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        baseline = baseline_assessment(case, selected, mode=mode)
        jev_payload: dict[str, object] | None = None
        if judge is not None:
            verdict = judge.verify_claim(
                query=case.query,
                claim=case.claim,
                contexts=list(selected.contexts),
            )
            jev_payload = {
                "provider": verdict.provider,
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "probabilities": verdict.raw["probabilities"],
                "requested_model": verdict.raw["requested_model"],
                "resolved_model": verdict.raw["resolved_model"],
                "latency_ms": verdict.raw["latency_ms"],
                "usage": verdict.raw["usage"],
                "reason": None,
                "matched_facts": [],
                "missing_facts": [],
                "conflicting_facts": [],
            }
        rows.append(
            {
                "case_id": case.case_id,
                "split": case.split,
                "category": case.category,
                "expected_verdict": case.expected_verdict,
                "input_audit": {
                    "sent_fields": ["query", "claim", "selected_evidence"],
                    "selected_evidence": list(selected.audit),
                    "state_sha256": hashlib.sha256(state_json.encode("utf-8")).hexdigest(),
                    "evaluation_label_sent": False,
                },
                "baseline": baseline,
                "jev": jev_payload,
            }
        )
    return {
        "experiment": "contexttrace_jev_claim_verification",
        "schema_version": "1.0",
        "stable_defaults_changed": False,
        "remote_provider": "typesafe_jev" if judge is not None else None,
        "rows": rows,
        "summary": summarize(rows),
    }


def summarize(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    materialized = list(rows)
    baseline_correct = sum(
        row["baseline"]["verdict"] == row["expected_verdict"]  # type: ignore[index]
        for row in materialized
    )
    jev_rows = [row for row in materialized if row.get("jev") is not None]
    disagreements: list[dict[str, str]] = []
    false_supported: list[str] = []
    unsupported_false_supported: list[str] = []
    for row in jev_rows:
        baseline_verdict = str(row["baseline"]["verdict"])  # type: ignore[index]
        jev_verdict = str(row["jev"]["verdict"])  # type: ignore[index]
        expected = str(row["expected_verdict"])
        case_id = str(row["case_id"])
        if baseline_verdict != jev_verdict:
            disagreements.append(
                {
                    "case_id": case_id,
                    "expected": expected,
                    "baseline": baseline_verdict,
                    "jev": jev_verdict,
                }
            )
        if expected != SUPPORTED and jev_verdict == SUPPORTED:
            false_supported.append(case_id)
        if expected == UNSUPPORTED and jev_verdict == SUPPORTED:
            unsupported_false_supported.append(case_id)

    latency_values = [float(row["jev"]["latency_ms"]) for row in jev_rows]  # type: ignore[index]
    jev_correct = sum(
        row["jev"]["verdict"] == row["expected_verdict"]  # type: ignore[index]
        for row in jev_rows
    )
    return {
        "cases": len(materialized),
        "baseline_accuracy": _ratio(baseline_correct, len(materialized)),
        "jev_run_complete": len(jev_rows) == len(materialized) and bool(materialized),
        "jev_accuracy": _ratio(jev_correct, len(jev_rows)) if jev_rows else None,
        "baseline_jev_disagreements": disagreements if jev_rows else None,
        "dangerous_false_supported_case_ids": false_supported if jev_rows else None,
        "unsupported_false_supported_case_ids": (
            unsupported_false_supported if jev_rows else None
        ),
        "mean_jev_latency_ms": round(statistics.fmean(latency_values), 3) if latency_values else None,
        "jev_total_input_tokens": _sum_usage(jev_rows, "input_tokens"),
        "jev_total_output_tokens": _sum_usage(jev_rows, "output_tokens"),
    }


def load_cases(path: str | Path, *, expected_split: str | None = None) -> list[ExperimentCase]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    split = str(payload.get("split") or "").strip()
    if split not in {"development", "heldout"}:
        raise JevExperimentError("%s must declare split as development or heldout." % source)
    if expected_split and split != expected_split:
        raise JevExperimentError("Expected %s split, got %s." % (expected_split, split))
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list) or not cases_payload:
        raise JevExperimentError("%s must contain a non-empty cases list." % source)

    cases: list[ExperimentCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(cases_payload):
        if not isinstance(item, dict):
            raise JevExperimentError("Case %s in %s must be an object." % (index, source))
        case_id = str(item.get("id") or "").strip()
        if not case_id or case_id in seen_ids:
            raise JevExperimentError("Case ids must be non-empty and unique: %r." % case_id)
        seen_ids.add(case_id)
        expected = str(item.get("expected_verdict") or "").strip()
        if expected not in ALLOWED_VERDICTS:
            raise JevExperimentError("Case %s has invalid expected_verdict %r." % (case_id, expected))
        contexts_payload = item.get("contexts")
        if not isinstance(contexts_payload, list) or not contexts_payload:
            raise JevExperimentError("Case %s must contain contexts." % case_id)
        contexts = tuple(
            TraceContext(id=str(context["id"]), text=str(context["text"]))
            for context in contexts_payload
        )
        cases.append(
            ExperimentCase(
                case_id=case_id,
                split=split,
                category=str(item.get("category") or expected),
                query=str(item.get("query") or ""),
                claim=str(item.get("claim") or ""),
                contexts=contexts,
                expected_verdict=expected,
            )
        )
    return cases


def enforce_remote_policy(*, local_only: bool, allow_remote: bool) -> None:
    if local_only:
        raise JevExperimentError(
            "Jev is remote and is blocked because ContextTrace local_only is enabled. "
            "Set CONTEXTTRACE_LOCAL_ONLY=false and pass --allow-remote for this experiment."
        )
    if not allow_remote:
        raise JevExperimentError(
            "Remote Jev calls require the explicit --allow-remote experiment flag."
        )


def create_live_judge(*, model: str) -> tuple[ExperimentalJevJudge, object]:
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise JevExperimentError("TYPESAFE_API_KEY is not set.")
    try:
        from typesafe_sdk import Choice, TypeSafeClient
    except ImportError as exc:
        raise JevExperimentError(
            "typesafe-sdk is not installed. Install benchmarks/jev_claim_verification/requirements.txt."
        ) from exc
    client = TypeSafeClient(
        api_key=api_key,
        base_url=os.environ.get("TYPESAFE_ENDPOINT") or None,
        timeout=120.0,
    )
    return ExperimentalJevJudge(client=client, choice_factory=Choice, model=model), client


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, help="Development or held-out JSON case file.")
    parser.add_argument("--output", required=True, help="Path for the JSON result.")
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--model", default="jev-latest")
    parser.add_argument("--mode", default="semantic", choices=("lexical", "semantic"))
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Validate selection and run the stable verifier without making a remote request.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Explicitly permit selected claim/evidence payloads to be sent to TypeSafe.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cases = load_cases(args.cases, expected_split=args.split)
    judge: ExperimentalJevJudge | None = None
    client: object | None = None
    if not args.baseline_only:
        config = load_config()
        enforce_remote_policy(local_only=config.local_only, allow_remote=args.allow_remote)
        judge, client = create_live_judge(model=args.model)
    try:
        result = run_experiment(cases, judge=judge, mode=args.mode)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print("wrote %s" % output)
    return 0


def _probability_map(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise JevExperimentError("TypeSafe verdict probabilities were missing or invalid.")
    probabilities: dict[str, float] = {}
    for key, raw_probability in value.items():
        label = str(key).strip().lower()
        if label not in ALLOWED_VERDICTS:
            raise JevExperimentError("TypeSafe returned an unknown probability label: %r." % label)
        probabilities[label] = _unit_float(raw_probability, field="probability[%s]" % label)
    return {label: probabilities[label] for label in LABELS if label in probabilities}


def _unit_float(value: object, *, field: str) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise JevExperimentError("TypeSafe %s was not numeric." % field) from exc
    if not 0.0 <= parsed <= 1.0:
        raise JevExperimentError("TypeSafe %s must be between 0 and 1." % field)
    return parsed


def _optional_nonnegative_int(value: object) -> int | None:
    if value is None:
        return None
    parsed = int(value)  # type: ignore[arg-type]
    if parsed < 0:
        raise JevExperimentError("TypeSafe token usage cannot be negative.")
    return parsed


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _sum_usage(rows: Iterable[dict[str, object]], field: str) -> int | None:
    values = [row["jev"]["usage"][field] for row in rows]  # type: ignore[index]
    if not values or any(value is None for value in values):
        return None
    return sum(int(value) for value in values)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (JevExperimentError, OSError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        raise SystemExit(2)
