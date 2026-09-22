from __future__ import annotations

from contexttrace.verify.atomic_coverage import (
    AtomicCoverageJudge,
    RequirementCoverage,
    aggregate_coverage,
    decompose_atomic_requirements,
)
from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import TraceContext


class FakeLocalNLI:
    provider = "local_atomic_test"
    model = "fixture"

    def verify_claim(self, *, query, claim, contexts):
        del query
        premise = contexts[0].text.casefold()
        supported = all(word in premise for word in _keywords(claim))
        scores = (
            {"entailment": 0.9, "contradiction": 0.03, "neutral": 0.07}
            if supported
            else {"entailment": 0.1, "contradiction": 0.05, "neutral": 0.85}
        )
        label = max(scores, key=scores.get)
        return JudgeVerdict(
            verdict="supported" if supported else "unsupported",
            confidence=scores[label],
            reason="fixture",
            provider=self.provider,
            model=self.model,
            raw={"nli_scores": scores, "nli_label": label},
        )


def _keywords(value: str) -> list[str]:
    return [word.strip(".,").casefold() for word in value.split() if len(word.strip(".,")) > 5]


def test_atomic_coverage_requires_every_requirement() -> None:
    judge = AtomicCoverageJudge(nli=FakeLocalNLI())
    verdict = judge.verify_claim(
        query="",
        claim="The policy provides backups and supports encryption.",
        contexts=[TraceContext(id="policy", text="The policy provides backups every day.")],
    )

    assert verdict.verdict == "partially_supported"
    assert verdict.raw["coverage_summary"] == {
        "requirements": 2,
        "covered": 1,
        "missing": 1,
        "contradicted": 0,
    }
    assert verdict.raw["remote_inference"] is False
    assert verdict.raw["automatic_supported"] is False


def test_decomposition_preserves_claim_substrings() -> None:
    claim = "The release restored the songs, making it the first unaltered edition."
    requirements = decompose_atomic_requirements(claim)

    assert requirements == [
        "The release restored the songs.",
        "making it the first unaltered edition.",
    ]
    assert all(requirement.rstrip(".") in claim for requirement in requirements)


def test_decomposition_does_not_reconstruct_shared_subject() -> None:
    claim = (
        "Mad Love's reputation has grown over the years, and it is viewed "
        "positively by modern critics."
    )

    requirements = decompose_atomic_requirements(claim)

    assert requirements == [
        "Mad Love's reputation has grown over the years.",
        "it is viewed positively by modern critics.",
    ]
    assert all(requirement.rstrip(".") in claim for requirement in requirements)


def test_aggregate_marks_complete_coverage_supported() -> None:
    rows = [
        RequirementCoverage(
            requirement="A.",
            status="covered",
            confidence=0.91,
            evidence_context_ids=("a",),
            evidence_texts=("A.",),
            nli_scores={"entailment": 0.91, "contradiction": 0.02, "neutral": 0.07},
            nli_label="entailment",
        ),
        RequirementCoverage(
            requirement="B.",
            status="covered",
            confidence=0.82,
            evidence_context_ids=("b",),
            evidence_texts=("B.",),
            nli_scores={"entailment": 0.82, "contradiction": 0.03, "neutral": 0.15},
            nli_label="entailment",
        ),
    ]

    assert aggregate_coverage(rows) == ("supported", 0.82, "all_requirements_covered")
