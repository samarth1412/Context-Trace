from contexttrace.verify.calibration import run_judge_calibration
from contexttrace.verify.judges import JudgeVerdict


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
