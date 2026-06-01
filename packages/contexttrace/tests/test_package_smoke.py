from importlib import metadata

import contexttrace
from contexttrace import AsyncContextTrace, ContextTrace, ReliabilityScorer


def test_package_exports_core_public_api():
    assert contexttrace.__version__ == "0.1.0"
    assert ContextTrace is not None
    assert AsyncContextTrace is not None
    assert ReliabilityScorer().score(
        citation_support=1.0,
        unsupported_claim_rate=0.0,
        failure_rate=0.0,
    ).grade == "A"


def test_installed_distribution_metadata_when_available():
    try:
        version = metadata.version("contexttrace")
    except metadata.PackageNotFoundError:
        version = contexttrace.__version__

    assert version == contexttrace.__version__
