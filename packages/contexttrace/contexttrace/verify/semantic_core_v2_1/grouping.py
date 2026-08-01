"""Conservative grouped-claim routing for the local NLI cascade."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2.cascade import (
    DeterministicDecision,
    deterministic_decision,
)
from contexttrace.verify.semantic_core_v2.claims import ClaimUnit

from .profile import V21Profile

GROUPED_CLAIM_NLI_VERSION = "grouped-claim-nli-v1.0.0"


class GroupedClaimNLI:
    """Resolve ordered same-source ambiguous claims with one NLI decision.

    A grouped entailment can safely support each conjunct. Any other grouped
    outcome is deliberately converted to ``unverifiable`` because a group-level
    neutral or contradiction cannot identify which member failed.
    """

    provider = "contexttrace_grouped_claim_nli"

    def __init__(
        self,
        base: ClaimJudge,
        *,
        trace: RAGTrace,
        claims: list[ClaimUnit],
        profile: V21Profile,
    ) -> None:
        self._base = base
        self._profile = profile
        self.model = getattr(base, "model", None)
        self._prepared: dict[str, list[JudgeVerdict]] = defaultdict(list)
        decisions = [deterministic_decision(claim, trace, profile) for claim in claims]
        for group in _claim_groups(claims, decisions, profile):
            self._prepare_group(trace, group)

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        prepared = self._prepared.get(claim)
        if prepared:
            return prepared.pop(0)
        return self._base.verify_claim(
            query=query,
            claim=claim,
            contexts=contexts,
        )

    def _prepare_group(
        self,
        trace: RAGTrace,
        group: list[tuple[ClaimUnit, DeterministicDecision]],
    ) -> None:
        contexts = _group_contexts(group, self._profile)
        if not contexts:
            return
        group_claim = " ".join(
            claim.verification_text.strip() for claim, _ in group
        ).strip()
        group_id = _group_id(group, contexts)
        try:
            base = self._base.verify_claim(
                query=trace.query,
                claim=group_claim,
                contexts=contexts,
            )
        except Exception:  # noqa: BLE001 - grouped provider failures fail closed
            base = JudgeVerdict(
                verdict="unverifiable",
                confidence=0.0,
                reason="Grouped NLI execution failed closed.",
                provider=self.provider,
                model=self.model,
                raw={"nli_label": "group_unresolved"},
            )

        raw_label = str(base.raw.get("nli_label") or "").casefold()
        entailed = bool(
            base.verdict == "supported"
            and raw_label == "entailment"
            and float(base.confidence)
            >= self._profile.grouped_nli_entailment_confidence
        )
        group_record = {
            "version": GROUPED_CLAIM_NLI_VERSION,
            "group_id": group_id,
            "group_size": len(group),
            "resolution": "entailed" if entailed else "unresolved",
            "base_verdict": base.verdict,
            "base_nli_label": base.raw.get("nli_label"),
            "base_confidence": round(float(base.confidence), 6),
        }
        for claim, _ in group:
            raw: dict[str, Any] = dict(base.raw)
            raw["grouped_claim_nli"] = dict(group_record)
            if not entailed:
                raw["nli_label"] = "group_unresolved"
            self._prepared[claim.verification_text].append(
                JudgeVerdict(
                    verdict="supported" if entailed else "unverifiable",
                    confidence=float(base.confidence) if entailed else 0.0,
                    reason=(
                        "One bounded grouped NLI decision entailed every claim."
                        if entailed
                        else "The grouped NLI decision could not safely attribute a "
                        "failure to an individual claim."
                    ),
                    matched_facts=[claim.verification_text] if entailed else [],
                    missing_facts=[] if entailed else [claim.verification_text],
                    provider=self.provider,
                    model=base.model,
                    raw=raw,
                )
            )


def prepare_grouped_nli(
    trace: RAGTrace,
    claims: list[ClaimUnit],
    profile: V21Profile,
    nli: ClaimJudge | None,
) -> ClaimJudge | None:
    if nli is None or not profile.enable_nli or not profile.grouped_claim_nli:
        return nli
    return GroupedClaimNLI(nli, trace=trace, claims=claims, profile=profile)


def _claim_groups(
    claims: list[ClaimUnit],
    decisions: list[DeterministicDecision],
    profile: V21Profile,
) -> list[list[tuple[ClaimUnit, DeterministicDecision]]]:
    by_context: dict[str, list[tuple[ClaimUnit, DeterministicDecision]]] = {}
    for claim, decision in zip(claims, decisions, strict=True):
        context_id = decision.match.context_id
        required_facts = list(decision.signals.get("required_facts") or [])
        missing_facts = list(decision.signals.get("missing_facts") or [])
        conflicting_facts = list(decision.signals.get("conflicting_facts") or [])
        eligible = bool(
            decision.requires_nli
            and context_id
            and required_facts
            and not missing_facts
            and not conflicting_facts
        )
        if eligible:
            by_context.setdefault(str(context_id), []).append((claim, decision))

    groups: list[list[tuple[ClaimUnit, DeterministicDecision]]] = []
    for run in by_context.values():
        start = 0
        while len(run) - start >= 2:
            remaining = len(run) - start
            size = min(profile.max_grouped_nli_claims, remaining)
            if remaining == profile.max_grouped_nli_claims + 1:
                size = 2
            groups.append(run[start : start + size])
            start += size
    return groups


def _group_contexts(
    group: list[tuple[ClaimUnit, DeterministicDecision]],
    profile: V21Profile,
) -> list[TraceContext]:
    contexts: list[TraceContext] = []
    seen: set[tuple[str, object, object]] = set()
    for _, decision in group:
        spans = list(decision.match.supporting_spans or [])[
            : profile.max_grouped_nli_spans_per_claim
        ]
        if not spans:
            span = decision.match.span_dict()
            spans = [span] if span else []
        added = False
        for span in spans:
            context_id = str(
                span.get("context_id") or decision.match.context_id or ""
            ).strip()
            text = str(span.get("text") or "").strip()
            key = (context_id, span.get("start_char"), span.get("end_char"))
            if not context_id or not text or key in seen:
                continue
            seen.add(key)
            contexts.append(
                TraceContext(
                    id=context_id,
                    text=text,
                    metadata={
                        "evidence_scope": "bounded_grouped_selected_span",
                        "start_char": span.get("start_char"),
                        "end_char": span.get("end_char"),
                        "span_hash": span.get("span_hash"),
                    },
                )
            )
            added = True
        if not added:
            return []
    return contexts


def _group_id(
    group: list[tuple[ClaimUnit, DeterministicDecision]],
    contexts: list[TraceContext],
) -> str:
    payload = {
        "claims": [claim.id for claim, _ in group],
        "contexts": [
            {
                "id": context.id,
                "start_char": context.metadata.get("start_char"),
                "end_char": context.metadata.get("end_char"),
            }
            for context in contexts
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "group_" + hashlib.sha256(raw).hexdigest()[:16]
