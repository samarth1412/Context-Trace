from contexttrace.verify.triage import build_triage_summary, render_triage_summary
from contexttrace.cli import main
import json


def test_triage_summary_prioritizes_failed_claim_and_one_fix():
    result = {
        "summary": {
            "failure_type": "partial_support",
            "should_abstain": False,
            "suggested_fix": "Remove the unsupported date.",
        },
        "claims": [
            {
                "claim": "The release was June 4.",
                "verdict": "unsupported",
                "confidence": 0.88,
                "evidence": "The release was June 3.",
                "citation_status": "citation_aligned",
                "root_cause": {
                    "reason": "The date is not supported.",
                    "suggested_fix": "Correct the date.",
                },
            }
        ],
    }

    triage = build_triage_summary(result)
    rendered = render_triage_summary(result)

    assert triage["one_next_fix"] == "Correct the date."
    assert triage["risk_level"] == "medium"
    assert "Developer Triage Summary" in rendered
    assert "Regression test:" in rendered


def test_verify_cli_triage_format(tmp_path, capsys):
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps(
            {
                "query": "When is the refund deadline?",
                "answer": "Refunds are available for 90 days.",
                "contexts": [{"id": "policy", "text": "Refunds are available for 30 days."}],
                "citations": [],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace), "--mode", "semantic", "--format", "triage"]) == 0
    output = capsys.readouterr().out
    assert "Developer Triage Summary" in output
    assert "One next fix:" in output
