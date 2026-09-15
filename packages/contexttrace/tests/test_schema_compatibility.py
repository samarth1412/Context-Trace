import json
from pathlib import Path

from jsonschema import Draft202012Validator

from contexttrace import load_json_schema
from contexttrace.capture import capture_rag_trace
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import load_trace, load_trace_file


FIXTURE = Path(__file__).parent / "fixtures" / "trace-v1.0.json"


def test_trace_v1_golden_round_trip_is_stable():
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))

    loaded = load_trace_file(FIXTURE)

    assert loaded.to_dict() == golden


def test_trace_v1_golden_conforms_to_packaged_schema():
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    schema = load_json_schema("TraceV1")

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(golden)


def test_trace_v1_loader_preserves_declared_provenance():
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden["taxonomy_version"] = "1.0-fixture"
    golden["verifier_version"] = "semantic_v1_fixture"
    golden["profile_id"] = "compatibility_fixture"

    emitted = load_trace(golden, source="compatibility fixture").to_dict()
    assert emitted["taxonomy_version"] == "1.0-fixture"
    assert emitted["verifier_version"] == "semantic_v1_fixture"
    assert emitted["profile_id"] == "compatibility_fixture"


def test_current_claim_verification_conforms_to_v1_schema():
    trace = capture_rag_trace(
        query="Which API version should I use?",
        answer="Use API version 1.0.",
        contexts=[
            {"id": "old", "text": "API version 1.0 supports this operation."},
            {"id": "new", "text": "API version 2.0 replaced version 1.0."},
        ],
    )
    result = verify_trace(trace, mode="semantic")
    schema = load_json_schema("ClaimVerificationV1")

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    assert "diagnostic_reasoner_version" not in result
