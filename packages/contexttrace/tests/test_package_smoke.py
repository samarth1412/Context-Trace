from pathlib import Path

import contexttrace
from contexttrace import AsyncContextTrace, ContextTrace, ReliabilityScorer


def test_package_exports_core_public_api():
    assert contexttrace.__version__ == "0.3.0"
    assert ContextTrace is not None
    assert AsyncContextTrace is not None
    assert ReliabilityScorer().score(
        citation_support=1.0,
        unsupported_claim_rate=0.0,
        failure_rate=0.0,
    ).grade == "A"


def test_source_distribution_metadata_matches_public_version():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"

    assert 'version = "%s"' % contexttrace.__version__ in pyproject.read_text(encoding="utf-8")
