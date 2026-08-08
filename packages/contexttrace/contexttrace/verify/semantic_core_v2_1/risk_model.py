"""Tiny learned support-risk gate for the dedicated v2.1 checker."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from importlib import resources
from typing import Any

from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.schema import TraceContext

from .checker import observable_conflicts

RISK_MODEL_RESOURCE = "support-risk-v1.json"
RISK_FEATURE_VERSION = "support-risk-features-v1.1.0"
RISK_FEATURE_NAMES = (
    "base_confidence",
    "nli_entailment",
    "nli_contradiction",
    "nli_neutral",
    "contradiction_signal",
    "omission_signal",
    "conflict_count_scaled",
)


@dataclass(frozen=True)
class SupportRiskModel:
    model_version: str
    feature_version: str
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float
    support_threshold: float
    reject_threshold: float
    payload_sha256: str

    def support_probability(self, features: dict[str, float]) -> float:
        ordered = [float(features[name]) for name in self.feature_names]
        standardized = [
            (value - mean) / scale
            for value, mean, scale in zip(
                ordered,
                self.means,
                self.scales,
                strict=True,
            )
        ]
        logit = self.intercept + sum(
            weight * value
            for weight, value in zip(self.weights, standardized, strict=True)
        )
        return round(_sigmoid(logit), 6)


class LearnedSupportRiskGate:
    """Use a hash-locked learned model to gate base support decisions."""

    provider = "contexttrace_learned_support_risk_gate"

    def __init__(
        self,
        base: ClaimJudge,
        model: SupportRiskModel | None = None,
    ) -> None:
        self._base = base
        self._model = model or load_support_risk_model()
        self.model = getattr(base, "model", None)

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        base = self._base.verify_claim(
            query=query,
            claim=claim,
            contexts=contexts,
        )
        if base.verdict != "supported":
            return base
        selected = _selected_context(base, contexts)
        if selected is None:
            return base
        evidence = _evidence_text(selected.text)
        features = extract_risk_features(claim, evidence, base)
        probability = self._model.support_probability(features)
        record = {
            "model_version": self._model.model_version,
            "feature_version": self._model.feature_version,
            "artifact_sha256": self._model.payload_sha256,
            "support_probability": probability,
            "support_threshold": self._model.support_threshold,
            "reject_threshold": self._model.reject_threshold,
        }
        eligible = bool(features["contradiction_signal"] or features["omission_signal"])
        record["eligible_for_intervention"] = eligible
        raw = dict(base.raw)
        raw["learned_support_risk"] = record
        if not eligible or probability >= self._model.support_threshold:
            return _copy_verdict(base, raw=raw)

        rejected = probability <= self._model.reject_threshold
        raw["nli_label"] = "neutral"
        raw["learned_support_risk"]["intervened"] = True
        return JudgeVerdict(
            verdict="unsupported" if rejected else "unverifiable",
            confidence=round(max(0.8, 1.0 - probability), 6),
            reason=(
                "The learned local risk gate rejected generic entailment."
                if rejected
                else "The learned local risk gate abstained on generic entailment."
            ),
            missing_facts=[claim],
            provider=self.provider,
            model=base.model,
            raw=raw,
        )


def extract_risk_features(
    claim: str,
    evidence: str,
    verdict: JudgeVerdict,
) -> dict[str, float]:
    scores = dict(verdict.raw.get("nli_scores") or {})
    conflicts = observable_conflicts(claim, evidence)
    contradiction_signal = any(
        conflict.resolution == "contradicted" for conflict in conflicts
    )
    omission_signal = any(
        conflict.resolution == "unsupported" for conflict in conflicts
    )
    return {
        "base_confidence": float(verdict.confidence),
        "nli_entailment": float(scores.get("entailment", 0.0)),
        "nli_contradiction": float(scores.get("contradiction", 0.0)),
        "nli_neutral": float(scores.get("neutral", 0.0)),
        "contradiction_signal": float(contradiction_signal),
        "omission_signal": float(omission_signal),
        "conflict_count_scaled": min(len(conflicts), 3) / 3.0,
    }


def load_support_risk_model() -> SupportRiskModel:
    payload = json.loads(
        resources.files("contexttrace.verify.semantic_core_v2_1.artifacts")
        .joinpath(RISK_MODEL_RESOURCE)
        .read_text(encoding="utf-8")
    )
    expected_hash = str(payload.get("payload_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    actual_hash = _canonical_sha256(unsigned)
    if not expected_hash or actual_hash != expected_hash:
        raise ValueError("Support-risk model artifact hash mismatch.")
    feature_names = tuple(payload["feature_names"])
    if feature_names != RISK_FEATURE_NAMES:
        raise ValueError("Support-risk model feature schema mismatch.")
    return SupportRiskModel(
        model_version=str(payload["model_version"]),
        feature_version=str(payload["feature_version"]),
        feature_names=feature_names,
        means=tuple(float(value) for value in payload["means"]),
        scales=tuple(float(value) for value in payload["scales"]),
        weights=tuple(float(value) for value in payload["weights"]),
        intercept=float(payload["intercept"]),
        support_threshold=float(payload["support_threshold"]),
        reject_threshold=float(payload["reject_threshold"]),
        payload_sha256=expected_hash,
    )


def _selected_context(
    verdict: JudgeVerdict,
    contexts: list[TraceContext],
) -> TraceContext | None:
    context_id = str(verdict.raw.get("context_id") or "").strip()
    if context_id:
        for context in contexts:
            if context.id == context_id:
                return context
    if len(contexts) == 1:
        return contexts[0]
    return None


def _evidence_text(text: str) -> str:
    value = str(text or "")
    marker = "\nEvidence: "
    if value.startswith("Question: ") and marker in value:
        return value.split(marker, 1)[1]
    return value


def _copy_verdict(base: JudgeVerdict, *, raw: dict[str, Any]) -> JudgeVerdict:
    return JudgeVerdict(
        verdict=base.verdict,
        confidence=base.confidence,
        reason=base.reason,
        matched_facts=list(base.matched_facts),
        missing_facts=list(base.missing_facts),
        conflicting_facts=list(base.conflicting_facts),
        provider=base.provider,
        model=base.model,
        raw=raw,
    )


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
