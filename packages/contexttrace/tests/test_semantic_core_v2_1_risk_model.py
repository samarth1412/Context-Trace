from __future__ import annotations

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2_1 import (
    LearnedSupportRiskGate,
    load_support_risk_model,
)


class EntailingNLI:
    provider = "synthetic_nli"
    model = "synthetic-model"

    def verify_claim(self, *, query, claim, contexts):
        del query, claim
        return JudgeVerdict(
            verdict="supported",
            confidence=0.95,
            reason="synthetic entailment",
            provider=self.provider,
            model=self.model,
            raw={
                "nli_label": "entailment",
                "nli_scores": {
                    "entailment": 0.95,
                    "contradiction": 0.02,
                    "neutral": 0.03,
                },
                "context_id": contexts[0].id,
            },
        )


def test_packaged_risk_model_is_hash_locked_and_complete() -> None:
    model = load_support_risk_model()

    assert model.model_version == "contexttrace-support-risk-v1.1.0"
    assert len(model.feature_names) == len(model.weights) == 7
    assert len(model.means) == len(model.scales) == 7
    assert model.payload_sha256


def test_learned_gate_preserves_high_confidence_exact_support() -> None:
    result = LearnedSupportRiskGate(EntailingNLI()).verify_claim(
        query="Which format is supported?",
        claim="The SDK supports JSON.",
        contexts=[TraceContext(id="sdk", text="The SDK supports JSON.")],
    )

    assert result.verdict == "supported"
    assert result.provider == "synthetic_nli"
    assert result.raw["learned_support_risk"]["support_probability"] >= 0.5


def test_learned_gate_rejects_scope_omission_false_entailment() -> None:
    result = LearnedSupportRiskGate(EntailingNLI()).verify_claim(
        query="Is encryption optional?",
        claim="Encryption is optional.",
        contexts=[
            TraceContext(
                id="encryption",
                text="Encryption is optional for local development.",
            )
        ],
    )

    assert result.verdict == "unsupported"
    risk = result.raw["learned_support_risk"]
    assert risk["intervened"] is True
    assert risk["support_probability"] <= risk["reject_threshold"]


def test_learned_gate_abstains_inside_uncertainty_band() -> None:
    model = load_support_risk_model()
    uncertain_model = type(model)(
        model_version=model.model_version,
        feature_version=model.feature_version,
        feature_names=model.feature_names,
        means=model.means,
        scales=model.scales,
        weights=tuple(0.0 for _ in model.weights),
        intercept=0.0,
        support_threshold=0.6,
        reject_threshold=0.4,
        payload_sha256=model.payload_sha256,
    )

    result = LearnedSupportRiskGate(EntailingNLI(), uncertain_model).verify_claim(
        query="Is encryption optional?",
        claim="Encryption is optional.",
        contexts=[
            TraceContext(
                id="encryption",
                text="Encryption is optional for local development.",
            )
        ],
    )

    assert result.verdict == "unverifiable"
