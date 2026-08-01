"""Versioned safety policy layered over the frozen semantic_core_v2 candidate."""

from __future__ import annotations

from dataclasses import dataclass

from contexttrace.verify.semantic_core_v2.profile import V2Profile


@dataclass(frozen=True)
class V21Profile(V2Profile):
    """A schema-compatible profile whose hash includes the promotion policy."""

    id: str = "selective_v2_1_safety"
    prevent_nli_only_green_promotion: bool = True


SELECTIVE_V2_1_PROFILE = V21Profile()
