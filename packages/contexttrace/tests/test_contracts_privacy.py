import json
import sqlite3
import stat
from contextlib import closing

from contexttrace import (
    ContextTrace,
    PrivacyPolicy,
    build_regression_case,
    capture_rag_trace,
    load_json_schema,
)
from contexttrace.diagnose import diagnose_payload
from contexttrace.repair import build_repair_plan
from contexttrace.verify.runner import VerificationLimits, verify_trace, verify_traces


PROVENANCE = {"schema_version", "taxonomy_version", "verifier_version", "profile_id"}


class ReverseCipher:
    def encrypt(self, plaintext):
        return plaintext[::-1]

    def decrypt(self, ciphertext):
        return ciphertext[::-1]


def _trace_payload():
    return {
        "query": "What is the policy?",
        "answer": "Refunds are available within 30 days.",
        "contexts": [{"id": "policy", "text": "Refunds are available within 30 days."}],
    }


def test_public_artifacts_have_packaged_v1_contracts(tmp_path):
    trace = capture_rag_trace(
        query="What is the policy?",
        answer="Refunds are available within 30 days.",
        contexts=[{"id": "policy", "text": "Refunds are available within 30 days."}],
    )
    verification = verify_trace(trace, mode="semantic")
    diagnosis = diagnose_payload(trace.to_dict())
    regression = build_regression_case(
        case_id="policy_1",
        trace=trace.to_dict(),
        expected={"status": "passed"},
    )
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(trace.to_dict()), encoding="utf-8")
    repair = build_repair_plan(trace_path)

    artifacts = {
        "TraceV1": trace.to_dict(),
        "ClaimVerificationV1": verification,
        "DiagnosisV1": diagnosis,
        "RepairPlanV1": repair,
        "RegressionCaseV1": regression,
    }
    for name, artifact in artifacts.items():
        schema = load_json_schema(name)
        assert schema["title"] == name
        assert PROVENANCE <= artifact.keys()
        assert artifact["schema_version"] == "1.0"
        assert artifact["verifier_version"] == "semantic_v1_calibrated"


def test_strict_privacy_covers_query_claim_metadata_and_agent_values(tmp_path):
    ct = ContextTrace(
        project="private",
        storage_path=str(tmp_path / "trace.db"),
        privacy="strict",
    )
    with ct.trace(query="patient@example.com", metadata={"patient": "Ada"}) as trace:
        trace.log_retrieval(
            [{"chunk_id": "secret-id", "content": "Patient diagnosis", "source": "/private/a"}]
        )
        trace.log_context(chunk_ids=["secret-id"])
        trace.log_answer("Sensitive answer", metadata={"ticket": "abc"})
        trace.log_citations([{"claim": "Sensitive claim", "source_chunk_id": "secret-id"}])
        trace.log_tool_result(
            "patient_lookup",
            input_json={"email": "patient@example.com"},
            output_json={"diagnosis": "sensitive"},
        )

    fetched = trace.fetch()
    assert fetched["query"] == "[query redacted]"
    assert fetched["metadata"] == {}
    assert fetched["chunks"][0]["content"] == "[chunk text redacted]"
    assert fetched["chunks"][0]["chunk_id"].startswith("id_sha256_")
    assert fetched["chunks"][0]["selected"] is True
    assert fetched["answer"]["answer"] == "[answer text redacted]"
    assert fetched["citation_checks"][0]["claim"] == "[citation claim redacted]"
    assert fetched["agent_events"][0]["input_json"]["email"] == "[tool input redacted]"
    assert fetched["agent_events"][0]["output_json"]["diagnosis"] == "[tool output redacted]"


def test_regex_redaction_cipher_ttl_and_secure_permissions(tmp_path):
    database = tmp_path / "private" / "trace.db"
    policy = PrivacyPolicy(
        redaction_patterns=(r"[\w.+-]+@[\w.-]+",),
        cipher=ReverseCipher(),
    )
    ct = ContextTrace(
        project="private",
        storage_path=str(database),
        privacy_policy=policy,
        retention_days=0,
    )
    with ct.trace(query="Email alice@example.com") as first:
        first.log_retrieval([{"chunk_id": "c1", "content": "Contact alice@example.com"}])
        first.log_answer("Sent to alice@example.com")
    assert first.fetch()["query"] == "Email [redacted]"
    assert first.fetch()["answer"]["answer"] == "Sent to [redacted]"

    with closing(sqlite3.connect(database)) as db:
        raw_query = db.execute("SELECT query FROM traces").fetchone()[0]
    assert raw_query.startswith("enc:")
    assert "alice@example.com" not in raw_query

    with ct.trace(query="Second trace") as second:
        second.log_answer("Second answer")
    assert [item["id"] for item in ct.list_traces()] == [second.trace_id]
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert stat.S_IMODE(database.parent.stat().st_mode) == 0o700


def test_batch_verification_reports_explicit_truncation():
    trace = capture_rag_trace(
        query="q",
        answer="A supported answer.",
        contexts=[
            {"id": "a", "text": "A supported answer."},
            {"id": "b", "text": "Additional evidence."},
        ],
    )
    results = verify_traces(
        [trace, trace],
        mode="semantic",
        limits=VerificationLimits(max_contexts=1, max_context_chars=8),
    )
    assert len(results) == 2
    assert results[0]["truncation"]["applied"] is True
    assert results[0]["truncation"]["contexts_used"] == 1
    assert results[0]["truncation"]["context_chars_used"] == 8
    assert results[0]["truncation"]["contexts_truncated"] is True


def test_nested_redaction_recurses_and_honors_metadata_allowlist():
    policy = PrivacyPolicy(
        metadata_allowlist=frozenset({"safe"}),
        redaction_patterns=(r"[\w.+-]+@[\w.-]+", r"token-[a-z0-9]+"),
        custom_redactors=(lambda text: text.replace("Ada", "[name]"),),
    )
    sanitized = policy.sanitize(
        "/v1/traces/t1/agent-events",
        {
            "name": "lookup",
            "input_json": {
                "users": [
                    {"email": "ada@example.com", "credentials": ("token-secret", "Ada")},
                ]
            },
            "output_json": {"nested": {"contact": "ada@example.com"}},
            "metadata": {
                "safe": {"owner": "Ada", "email": "ada@example.com"},
                "secret": "token-private",
            },
        },
    )

    assert sanitized["input_json"]["users"][0] == {
        "email": "[redacted]",
        "credentials": ["[redacted]", "[name]"],
    }
    assert sanitized["output_json"]["nested"]["contact"] == "[redacted]"
    assert sanitized["metadata"] == {
        "safe": {"owner": "[name]", "email": "[redacted]"},
    }


def test_verification_limits_oversized_answer_and_context_without_mutating_input():
    trace = capture_rag_trace(
        query="q",
        answer="answer-" * 100,
        contexts=[{"id": "large", "text": "context-" * 100}],
    )
    original = trace.to_dict()

    result = verify_trace(
        trace,
        mode="semantic",
        limits=VerificationLimits(max_answer_chars=17, max_context_chars=19),
    )

    assert result["truncation"]["applied"] is True
    assert result["truncation"]["answer_chars_used"] == 17
    assert result["truncation"]["context_chars_used"] == 19
    assert trace.to_dict() == original
