import pytest

from contexttrace.verify import RAGTrace, TraceContext, verify_trace
from contexttrace.verify.local_ml import LocalMLError, local_ml_similarity


def test_local_ml_hash_similarity_is_local_and_deterministic(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_LOCAL_ML_MODEL_PATH", raising=False)

    identical = local_ml_similarity("refunds within 30 days", "refunds within 30 days")
    unrelated = local_ml_similarity("refunds within 30 days", "vector payload indexes")

    assert identical == 1.0
    assert unrelated < identical


def test_local_ml_mode_is_accepted_by_verifier(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_LOCAL_ML_MODEL_PATH", raising=False)

    result = verify_trace(
        RAGTrace(
            query="Where does ContextTrace store traces?",
            answer="ContextTrace stores traces in .contexttrace/contexttrace.db.",
            contexts=[
                TraceContext(
                    id="docs/local-mode.md",
                    text="ContextTrace stores traces in .contexttrace/contexttrace.db.",
                )
            ],
        ),
        mode="local-ml",
    )

    assert result["summary"]["mode"] == "local_ml"
    assert result["claims"][0]["verdict"] == "supported"


def test_local_ml_model_path_must_be_local(monkeypatch, tmp_path):
    missing = tmp_path / "missing-model"
    monkeypatch.setenv("CONTEXTTRACE_LOCAL_ML_MODEL_PATH", str(missing))

    with pytest.raises(LocalMLError, match="existing local model"):
        local_ml_similarity("claim", "evidence")
