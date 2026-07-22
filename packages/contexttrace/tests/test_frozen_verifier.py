import hashlib
from pathlib import Path

from contexttrace.contracts import VERIFIER_VERSION


FROZEN_FACTS_SHA256 = "4fa507db2126423c8d0787811e78d0d6ffecf5d7603828b6a6d9b23ca8207bc4"


def test_semantic_v1_calibrated_implementation_is_frozen():
    implementation = Path(__file__).parents[1] / "contexttrace" / "verify" / "facts.py"
    digest = hashlib.sha256(implementation.read_bytes()).hexdigest()
    assert VERIFIER_VERSION == "semantic_v1_calibrated"
    assert digest == FROZEN_FACTS_SHA256, (
        "The calibrated verifier changed. Do not update this hash in response to calibration-set errors; "
        "create a new verifier version and preregister an untouched test manifest."
    )
