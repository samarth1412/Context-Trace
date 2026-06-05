import json

from contexttrace.cli import main
from contexttrace.verify.calibration import run_judge_calibration
from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.local_nli import LocalNLIJudge, NLIResult
from contexttrace.verify.nli_calibration import (
    nli_calibration_failures,
    run_nli_calibration,
    write_nli_calibration_report,
)


class AlwaysSupportedJudge:
    provider = "unit"
    model = "always-supported"

    def verify_claim(self, *, query, claim, contexts):
        return JudgeVerdict(
            verdict="supported",
            confidence=0.99,
            reason="Unit judge always supports claims.",
            matched_facts=[claim],
            provider=self.provider,
            model=self.model,
        )


def test_judge_calibration_flags_dangerous_misses():
    result = run_judge_calibration(
        judge=AlwaysSupportedJudge(),
        case_set="contexttrace",
        min_exact_match_rate=1.0,
        min_contradiction_recall=1.0,
        max_dangerous_miss_rate=0.0,
    )

    assert result["status"] == "failed"
    assert result["judge"]["provider"] == "unit"
    assert result["scorecard"]["dangerous_cases"] > 0
    assert result["scorecard"]["dangerous_miss_rate"] > 0
    assert any("dangerous_miss_rate" in failure for failure in result["failures"])


def test_nli_calibration_flags_false_greens_and_reports_latency():
    nli = LocalNLIJudge(
        classifier=lambda premise, hypothesis: NLIResult(
            label="entailment",
            confidence=0.99,
            scores={"entailment": 0.99, "neutral": 0.01, "contradiction": 0.0},
            backend="unit",
        )
    )

    result = run_nli_calibration(
        nli=nli,
        case_set="contexttrace",
        min_exact_match_rate=1.0,
        min_entailment_precision=1.0,
        min_contradiction_recall=1.0,
        max_dangerous_miss_rate=0.0,
    )

    assert result["status"] == "failed"
    assert result["nli"]["provider"] == "local_nli"
    assert result["scorecard"]["nli_call_count"] > 0
    assert result["scorecard"]["case_latency_p95_ms"] >= 0.0
    assert result["scorecard"]["unsupported_as_supported_cases"] > 0
    assert result["scorecard"]["dangerous_miss_rate"] > 0
    assert any("dangerous_miss_rate" in failure for failure in result["failures"])


def test_nli_calibration_failure_thresholds_include_latency():
    failures = nli_calibration_failures(
        {
            "exact_match_rate": 0.9,
            "entailment_precision": 0.9,
            "contradiction_recall": 0.9,
            "dangerous_miss_rate": 0.0,
            "case_latency_p95_ms": 101.0,
        },
        min_exact_match_rate=0.8,
        min_entailment_precision=0.85,
        min_contradiction_recall=0.7,
        max_dangerous_miss_rate=0.05,
        max_p95_latency_ms=100.0,
    )

    assert failures == ["case_latency_p95_ms 101.000 > 100.000"]


def test_nli_calibration_report_generation(tmp_path):
    nli = LocalNLIJudge(
        classifier=lambda premise, hypothesis: NLIResult(label="neutral", confidence=0.9, backend="unit")
    )
    result = run_nli_calibration(
        nli=nli,
        case_set="contexttrace",
        min_exact_match_rate=0.0,
        min_entailment_precision=0.0,
        min_contradiction_recall=0.0,
        max_dangerous_miss_rate=1.0,
    )
    report_path = tmp_path / "nli-calibration.html"

    written = write_nli_calibration_report(result, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Local NLI Calibration" in html
    assert "Unsupported Marked Supported" in html
    assert "Raw JSON" in html


def test_nli_calibration_requires_local_model_without_provider(monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_NLI_MODEL_PATH", raising=False)

    assert main(["nli-calibrate", "--case-set", "contexttrace"]) == 2


def test_nli_calibration_cli_json_uses_runner(monkeypatch, capsys):
    def fake_run_nli_calibration(**kwargs):
        assert kwargs["case_set"] == "contexttrace"
        assert kwargs["backend"] == "auto"
        return {
            "status": "passed",
            "case_set": "contexttrace",
            "case_source": "unit",
            "cases": 1,
            "nli": {"provider": "local_nli", "model": "unit"},
            "thresholds": {},
            "scorecard": {
                "exact_match_rate": 1.0,
                "verdict_match_rate": 1.0,
                "citation_match_rate": 1.0,
                "abstention_match_rate": 1.0,
                "entailment_precision": 1.0,
                "entailment_recall": 1.0,
                "contradiction_recall": 1.0,
                "unsupported_like_recall": 1.0,
                "dangerous_miss_rate": 0.0,
                "unsupported_as_supported_cases": 0,
                "case_latency_p50_ms": 1.0,
                "case_latency_p95_ms": 1.0,
                "nli_call_latency_p50_ms": 1.0,
                "nli_call_latency_p95_ms": 1.0,
            },
            "failures": [],
            "dangerous_miss_rows": [],
            "unsupported_as_supported_rows": [],
            "benchmark": {},
        }

    monkeypatch.setattr("contexttrace.cli.run_nli_calibration", fake_run_nli_calibration)

    assert main(["nli-calibrate", "--case-set", "contexttrace", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "passed"
    assert output["nli"]["model"] == "unit"
