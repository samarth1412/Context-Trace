from copy import deepcopy
import json

import pytest

from contexttrace.cli import main
from contexttrace.verify.schema import VerificationInputError
from contexttrace.verify.suite import (
    add_trace_files_to_suite,
    create_suite_from_trace_files,
    load_suite_file,
    run_suite,
    write_suite_file,
)
from contexttrace.verify.suite_report import SuiteReportGenerator


def trace(query, answer, contexts, cited=0):
    return {"query": query, "answer": answer,
            "contexts": [{"id": f"document-{index}", "text": text}
                         for index, text in enumerate(contexts)],
            "citations": [{"claim": answer, "source_id": f"document-{cited}"}]}


def retention(*, old=False):
    answer = f"Operators should configure {30 if old else 14} days of retention."
    return trace("What retention period should operators configure?", answer, [
        "Operations guide version 1. Operators should configure 30 days of retention.",
        "Operations guide version 2. Operators should configure 14 days of retention.",
    ], cited=0 if old else 1)


def create(tmp_path, payload=None, verifier="hybrid_v2"):
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload or retention()))
    return create_suite_from_trace_files([str(path)], mode="semantic", verifier=verifier)


def replay(suite, payload, **kwargs):
    return run_suite(suite, endpoint="http://local.invalid/query", caller=lambda *_: payload, **kwargs)


def test_hybrid_suite_catches_stale_regression_and_accepts_repair(tmp_path):
    suite = create(tmp_path)
    path = tmp_path / "suite.json"
    write_suite_file(suite, path)
    suite = load_suite_file(path)
    assert suite["schema_version"] == "0.2"
    assert suite["verifier"] == "hybrid_v2"
    failed = replay(suite, retention(old=True))
    assert failed["summary"]["failed"] == 1
    assert failed["summary"]["should_abstain_cases"] == 1
    assert failed["summary"]["regressions"] == 1
    assert failed["verifier"] == "hybrid_v2"
    case = failed["cases"][0]
    for side in ("baseline", "current"):
        verification = case[side]["verification"]
        assert verification["verifier_version"] == "hybrid_v2"
        assert verification["schema_version"] == "2.0"
        assert verification["taxonomy_version"] == "contexttrace-hybrid-v2.0"
    assert replay(suite, retention())["summary"]["passed"] == 1


def test_legacy_suite_defaults_and_contract_remain_stable(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(retention()))
    suite = create_suite_from_trace_files([str(path)], mode="semantic")
    assert suite["schema_version"] == "0.1"
    assert "verifier" not in suite
    result = replay(suite, retention(old=True))
    assert "verifier" not in result
    assert result["summary"]["passed"] == 1
    assert result["cases"][0]["current"]["verification"]["verifier_version"] == "semantic_v1_calibrated"


def test_add_inherits_saved_verifier(tmp_path):
    suite = create(tmp_path)
    other = tmp_path / "other.json"
    other.write_text(json.dumps(retention(old=True)))
    updated = add_trace_files_to_suite(suite, [str(other)])["suite"]
    assert updated["verifier"] == "hybrid_v2"
    assert len(updated["cases"]) == 2
    assert all(case["baseline_qa"]["verification"]["verifier_version"] == "hybrid_v2"
               for case in updated["cases"])
    assert replay(updated, retention())["summary"]["passed"] == 2


@pytest.mark.parametrize("corruption", ["unknown", "mixed", "missing", "schema", "taxonomy"])
def test_invalid_or_mixed_verifiers_fail_before_endpoint_call(tmp_path, corruption):
    suite = create(tmp_path)
    if corruption == "unknown":
        suite["verifier"] = "not-a-verifier"
    elif corruption == "missing":
        suite.pop("verifier")
    else:
        verification = suite["cases"][0]["baseline_qa"]["verification"]
        verification[{"mixed": "verifier_version", "schema": "schema_version",
                      "taxonomy": "taxonomy_version"}[corruption]] = "incorrect"
    def forbidden(*_args):
        pytest.fail("Invalid suite must be rejected before making a request")
    with pytest.raises(VerificationInputError):
        run_suite(suite, endpoint="http://local.invalid/query", caller=forbidden)


def test_baseline_without_cache_uses_hybrid_and_mode_override_recomputes(tmp_path):
    suite = create(tmp_path)
    suite["cases"][0].pop("baseline_qa")
    result = replay(suite, retention(old=True))
    assert result["summary"]["failed"] == 1
    assert result["cases"][0]["baseline"]["verification"]["verifier_version"] == "hybrid_v2"
    suite = create(tmp_path)
    suite["cases"][0]["baseline_qa"]["summary"]["mode"] = "lexical"
    suite["cases"][0]["baseline_qa"]["verification"]["answer"] = "stale cached answer"
    result = replay(suite, retention())
    assert result["cases"][0]["baseline"]["verification"]["answer"] == retention()["answer"]


def test_hybrid_corpus_audit_is_explicitly_unsupported(tmp_path):
    suite = create(tmp_path)
    with pytest.raises(VerificationInputError, match="corpus"):
        replay(suite, retention(), corpus_path=tmp_path)


SOURCE_CASES = [
    ("historical", "What did operations guide version 1 recommend?",
     "Operators should configure 30 days of retention.",
     ["Operations guide version 1. Operators should configure 30 days of retention.",
      "Operations guide version 2. Operators should configure 14 days of retention."], False),
    ("lifecycle", "How should applications create a client?", "Applications should construct ClassicClient.",
     ["Applications should construct ClassicClient.",
      "ClassicClient is deprecated and replaced by NextClient. Applications should construct NextClient instead."], True),
    ("replacement", "Which client should applications use?", "Applications should construct NextClient.",
     ["ClassicClient is deprecated and replaced by NextClient. Applications should construct NextClient instead."], False),
    ("dated", "What retention period should operators configure?", "Operators should configure 30 days of retention.",
     ["Published 2024-01-10. Operators should configure 30 days of retention.",
      "Updated 2026-05-20. Operators should configure 14 days of retention."], True),
    ("conflict", "Does Atlas enable remote access by default?", "Atlas enables remote access by default.",
     ["Atlas enables remote access by default.", "Atlas disables remote access by default."], True),
    ("unrelated_version", "What does Widget export?", "Widget exports telemetry.",
     ["Widget exports telemetry.", "Billing handbook version 9. Invoices are retained for seven years."], False),
    ("no_chronology", "What does Widget export?", "Widget exports telemetry.", ["Widget exports telemetry."], False),
]


@pytest.mark.parametrize("_name,query,answer,contexts,blocked", SOURCE_CASES, ids=[case[0] for case in SOURCE_CASES])
def test_source_conditions_through_native_suite(tmp_path, _name, query, answer, contexts, blocked):
    payload = trace(query, answer, contexts)
    suite = create(tmp_path, payload)
    result = replay(suite, payload)
    assert result["summary"]["errors"] == 0
    assert result["summary"]["failed"] == int(blocked)


def test_cli_persists_hybrid_and_emits_failure_exit_and_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "clean.json"
    path.write_text(json.dumps(retention()))
    suite_path = tmp_path / "suite.json"
    assert main(["suite", "create", str(path), "--out", str(suite_path),
                 "--verifier", "hybrid_v2", "--mode", "semantic"]) == 0
    import contexttrace.capture_endpoint as capture
    monkeypatch.setattr(capture, "_default_caller", lambda *_: retention(old=True))
    assert main(["suite", "run", str(suite_path), "--endpoint", "http://local.invalid/query",
                 "--out", str(tmp_path / "results.json"), "--report-out", str(tmp_path / "report.html")]) == 1
    assert "hybrid_v2 (experimental)" in capsys.readouterr().out
    assert "hybrid_v2 (experimental)" in (tmp_path / "report.html").read_text()
    monkeypatch.setattr(capture, "_default_caller", lambda *_: retention())
    assert main(["suite", "run", str(suite_path), "--endpoint", "http://local.invalid/query",
                 "--out", str(tmp_path / "repaired.json")]) == 0


def test_report_escapes_verifier_identity(tmp_path):
    result = deepcopy(replay(create(tmp_path), retention()))
    result["verifier"] = "<script>alert(1)</script>"
    html = SuiteReportGenerator().render(result)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
