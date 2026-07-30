"""Identity-safe baselines for ContextTrace-Unseen-v1."""

from typing import Any, Mapping

from .contract import BaselineInputError, build_candidate_input


def score_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Lazily invoke the default deterministic lexical baseline."""

    from .lexical_overlap import score_candidate as _score_candidate

    return _score_candidate(candidate)

__all__ = [
    "BaselineInputError",
    "build_candidate_input",
    "score_candidate",
]
