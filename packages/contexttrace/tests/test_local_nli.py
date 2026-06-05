import json

import pytest

from contexttrace.cli import main
from contexttrace.verify import RAGTrace, TraceCitation, TraceContext, verify_trace
from contexttrace.verify.local_nli import (
    LocalNLIError,
    LocalNLIJudge,
    NLIResult,
    _canonical_label,
    build_nli_provider,
    local_nli_entailment,
)


def test_nli_mode_uses_local_claim_span_entailment():
    calls = []

    def classifier(premise, hypothesis):
        calls.append((premise, hypothesis))
        return NLIResult(
            label="entailment",
            confidence=0.94,
            scores={"entailment": 0.94, "neutral": 0.05, "contradiction": 0.01},
            backend="unit",
        )

    result = verify_trace(
        RAGTrace(
            query="How long does refund processing take?",
            answer="Refunds are processed within 5 business days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text=(
                        "Customers may request refunds within 30 days. "
                        "Refunds are processed within 5 business days."
                    ),
                )
            ],
            citations=[
                TraceCitation(
                    claim="Refunds are processed within 5 business days.",
                    source_id="policy",
                )
            ],
        ),
        mode="nli",
        nli=LocalNLIJudge(classifier=classifier),
    )

    claim = result["claims"][0]
    assert result["summary"]["mode"] == "nli"
    assert claim["verdict"] == "supported"
    assert claim["support_status"] == "grounded_by_span"
    assert claim["truth_status"] == "not_assessed"
    assert claim["citation_status"] == "citation_ok"
    assert claim["judge"]["provider"] == "local_nli"
    assert claim["judge"]["raw"]["nli_label"] == "entailment"
    assert calls[0] == (
        "Refunds are processed within 5 business days.",
        "Refunds are processed within 5 business days.",
    )


def test_nli_mode_sees_selected_span_not_full_context():
    premises = []

    def classifier(premise, hypothesis):
        del hypothesis
        premises.append(premise)
        return NLIResult(label="entailment", confidence=0.91, backend="unit")

    verify_trace(
        RAGTrace(
            query="What is the refund window?",
            answer="Refunds are available within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text=(
                        "Shipping takes 5 business days. "
                        "Refunds are available within 30 days. "
                        "Enterprise exceptions require manager review."
                    ),
                )
            ],
        ),
        mode="nli",
        nli=LocalNLIJudge(classifier=classifier),
    )

    assert premises == ["Refunds are available within 30 days."]


def test_nli_mode_maps_contradiction_to_claim_verdict():
    result = verify_trace(
        RAGTrace(
            query="What is the refund window?",
            answer="Refunds are available within 90 days.",
            contexts=[
                TraceContext(id="policy", text="Refunds are available within 30 days.")
            ],
        ),
        mode="nli",
        nli=LocalNLIJudge(
            classifier=lambda premise, hypothesis: NLIResult(
                label="contradiction",
                confidence=0.89,
                scores={"contradiction": 0.89, "neutral": 0.08, "entailment": 0.03},
                backend="unit",
            )
        ),
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_facts"] == ["Refunds are available within 90 days."]
    assert claim["judge"]["raw"]["nli_label"] == "contradiction"


def test_nli_mode_requires_explicit_local_model_or_provider(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_NLI_MODEL_PATH", raising=False)

    with pytest.raises(ValueError, match="CONTEXTTRACE_NLI_MODEL_PATH"):
        verify_trace(
            RAGTrace(
                query="What is the refund policy?",
                answer="Refunds are available within 30 days.",
                contexts=[
                    TraceContext(id="policy", text="Refunds are available within 30 days.")
                ],
            ),
            mode="nli",
        )


def test_nli_provider_rejects_missing_model_path(monkeypatch, tmp_path):
    missing = tmp_path / "missing-nli-model"
    monkeypatch.setenv("CONTEXTTRACE_NLI_MODEL_PATH", str(missing))

    with pytest.raises(LocalNLIError, match="existing local model"):
        build_nli_provider()

    with pytest.raises(LocalNLIError, match="existing local model"):
        local_nli_entailment(
            premise="Refunds are available within 30 days.",
            hypothesis="Refunds are available within 30 days.",
            model_path=str(missing),
        )


def test_nli_label_mapping_does_not_treat_not_entailment_as_supported():
    assert _canonical_label("not_entailment", index=0, total=2) == "neutral"
    assert _canonical_label("ENTAILMENT", index=1, total=2) == "entailment"
    assert _canonical_label("CONTRADICTION", index=0, total=3) == "contradiction"


def test_verify_cli_accepts_nli_mode_and_reports_missing_model(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_NLI_MODEL_PATH", raising=False)
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {"id": "policy", "text": "Refunds are available within 30 days."}
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--mode", "nli"]) == 2

    assert "CONTEXTTRACE_NLI_MODEL_PATH" in capsys.readouterr().err
