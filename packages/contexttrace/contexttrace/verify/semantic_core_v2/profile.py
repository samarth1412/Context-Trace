"""Versioned semantic_core_v2 profiles and thresholds."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .constants import PROFILE_VERSION


@dataclass(frozen=True)
class V2Thresholds:
    """Frozen operating thresholds selected before untouched-result access."""

    deterministic_accept_confidence: float = 0.86
    deterministic_strong_support_score: float = 0.68
    deterministic_exact_support_score: float = 0.62
    deterministic_conflict_score: float = 0.30
    deterministic_unsupported_score: float = 0.18
    nli_entailment_confidence: float = 0.80
    nli_contradiction_confidence: float = 0.80
    nli_neutral_confidence: float = 0.70
    green_confidence: float = 0.90
    low_authority_score: float = 0.40
    high_authority_score: float = 0.85

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one.")


@dataclass(frozen=True)
class V2Profile:
    id: str = "selective_v2"
    version: str = PROFILE_VERSION
    enable_nli: bool = True
    forced_classification: bool = False
    source_condition_features: bool = True
    citation_features: bool = True
    use_deterministic_on_nli_disagreement: bool = False
    max_nli_spans: int = 3
    max_nli_span_chars: int = 1600
    thresholds: V2Thresholds = field(default_factory=V2Thresholds)

    def __post_init__(self) -> None:
        if not 1 <= self.max_nli_spans <= 8:
            raise ValueError("max_nli_spans must be between 1 and 8.")
        if not 128 <= self.max_nli_span_chars <= 8192:
            raise ValueError("max_nli_span_chars must be between 128 and 8192.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def sha256(self) -> str:
        raw = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


SELECTIVE_V2_PROFILE = V2Profile()
DETERMINISTIC_ONLY_V2_PROFILE = replace(
    SELECTIVE_V2_PROFILE,
    id="deterministic_only_v2",
    enable_nli=False,
)
FORCED_CLASSIFICATION_V2_PROFILE = replace(
    SELECTIVE_V2_PROFILE,
    id="forced_classification_v2",
    forced_classification=True,
)
NO_SOURCE_CONDITION_V2_PROFILE = replace(
    SELECTIVE_V2_PROFILE,
    id="no_source_condition_v2",
    source_condition_features=False,
)
NO_CITATION_FEATURES_V2_PROFILE = replace(
    SELECTIVE_V2_PROFILE,
    id="no_citation_features_v2",
    citation_features=False,
)
NO_ROUTE_DISAGREEMENT_V2_PROFILE = replace(
    SELECTIVE_V2_PROFILE,
    id="no_route_disagreement_v2",
    use_deterministic_on_nli_disagreement=True,
)

PROFILES = {
    profile.id: profile
    for profile in (
        SELECTIVE_V2_PROFILE,
        DETERMINISTIC_ONLY_V2_PROFILE,
        FORCED_CLASSIFICATION_V2_PROFILE,
        NO_SOURCE_CONDITION_V2_PROFILE,
        NO_CITATION_FEATURES_V2_PROFILE,
        NO_ROUTE_DISAGREEMENT_V2_PROFILE,
    )
}


def profile_for_id(profile_id: str) -> V2Profile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown semantic_core_v2 profile: {profile_id}") from exc
