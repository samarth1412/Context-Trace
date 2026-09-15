import pytest

from contexttrace.verify.hybrid_v2 import verify_trace_hybrid_v2
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext


def verify(query, answer, contexts, *, cited=0):
    trace = RAGTrace(
        query=query,
        answer=answer,
        contexts=[TraceContext(id=f"source-{index}", text=text) for index, text in enumerate(contexts)],
        citations=[TraceCitation(claim=answer, source_id=f"source-{cited}")],
    )
    result = verify_trace_hybrid_v2(trace, mode="semantic")
    blocked = result["abstention"]["should_abstain"] or any(
        claim["verdict"] != "supported" or claim["citation_status"] != "citation_ok"
        for claim in result["claims"]
    )
    return blocked, result


@pytest.mark.parametrize(
    ("query", "control", "fault", "context"),
    [
        (
            "What is the request timeout for Harbor?",
            "Harbor has a request timeout of 12 seconds.",
            "Harbor has a request timeout of 30 seconds.",
            '{"service":"Harbor","request_timeout_seconds":12,"retry_limit":3}',
        ),
        (
            "How much storage does the Basic plan include?",
            "The Basic plan includes 5 GB of storage.",
            "The Basic plan includes 50 GB of storage.",
            "| Plan | Storage |\n| --- | --- |\n| Basic | 5 GB |\n| Pro | 50 GB |",
        ),
        (
            "In which region is the analytics cluster located?",
            "The analytics cluster is located in eu-west-1.",
            "The analytics cluster is located in us-east-1.",
            "cluster,region\nanalytics,eu-west-1\ntransactional,us-east-1",
        ),
    ],
)
def test_structured_bindings_accept_target_value_and_reject_other_value(query, control, fault, context):
    assert verify(query, control, [context])[0] is False
    blocked, result = verify(query, fault, [context])
    assert blocked is True
    assert result["claims"][0]["verdict"] == "contradicted"


def test_conditional_exception_rejects_permission_outside_exception():
    context = "Unopened items may be returned within 14 days. Opened items cannot be returned unless they arrived damaged."
    control = "Opened, undamaged items cannot be returned."
    fault = "Opened, undamaged items may be returned within 14 days."
    assert verify("Can an opened, undamaged item be returned?", control, [context])[0] is False
    blocked, result = verify("Can an opened, undamaged item be returned?", fault, [context])
    assert blocked is True
    assert "conditional_exception" in result["claims"][0]["reason"]


def test_prohibited_operation_order_is_not_treated_as_support():
    context = (
        "Worker restart runbook:\n1. Pause intake.\n2. Drain queued jobs.\n3. Restart the worker.\n"
        "Never restart the worker before draining queued jobs."
    )
    control = "Operators must drain queued jobs before restarting the worker."
    fault = "Operators should restart the worker before draining queued jobs."
    assert verify("What must operators do before restarting the worker?", control, [context])[0] is False
    blocked, result = verify("What must operators do before restarting the worker?", fault, [context])
    assert blocked is True
    assert "prohibited_operation_order" in result["claims"][0]["reason"]


def test_exclusive_feature_scope_handles_negative_and_positive_claims():
    context = "Starter includes CSV exports only. PDF exports are available on the Business plan."
    control = "The Starter plan does not include PDF exports."
    fault = "The Starter plan includes PDF exports."
    assert verify("Can the Starter plan export PDF reports?", control, [context])[0] is False
    assert verify("Can the Starter plan export PDF reports?", fault, [context])[0] is True


def test_named_source_question_does_not_merge_another_guide_as_a_conflict():
    contexts = [
        "The installation guide says remote access is enabled by default.",
        "The security guide says remote access is disabled by default. Neither guide supersedes the other.",
    ]
    attributed = "The installation guide says remote access is enabled by default."
    assert verify("What does the installation guide say about remote access?", attributed, contexts)[0] is False
    overclaim = "Both guides say remote access is enabled by default."
    assert verify("What does the installation guide say about remote access?", overclaim, contexts)[0] is True
    unscoped = "Remote access is enabled by default."
    assert verify("Is remote access enabled by default?", unscoped, contexts)[0] is True


def test_historical_use_does_not_conflict_with_current_retirement_instruction():
    contexts = [
        "Before the migration, the service used key cedar-2024.",
        "Migration completed: key cedar-2024 is retired. Operators must use key cedar-2026 and must not reuse key cedar-2024.",
    ]
    answer = "Operators must use key cedar-2026 and must not reuse key cedar-2024."
    assert verify("What should operators do with the retired session key?", answer, contexts, cited=1)[0] is False
