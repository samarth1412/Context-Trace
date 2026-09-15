#!/usr/bin/env python3
"""Build the public ContextTrace investigations and animated terminal demos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
INVESTIGATIONS = ROOT / "examples" / "investigations"
VIDEOS = ROOT / "docs" / "assets" / "demos"


CASES = [
    {
        "slug": "stale-but-supported",
        "title": "A grounded answer backed by an expired policy",
        "question": "What is the current Acme Transit cancellation window?",
        "signal": "grounded_but_stale",
        "broken": {
            "query": "What is the current Acme Transit cancellation window?",
            "answer": "Acme Transit passes may be cancelled within 45 days of purchase.",
            "contexts": [{
                "id": "transit_policy_2024",
                "text": "Acme Transit passes may be cancelled within 45 days of purchase.",
                "metadata": {
                    "source": "transit-cancellations.md", "version": "2024",
                    "source_status": "stale", "canonical": False, "authority_score": 0.8,
                },
            }],
            "citations": [{
                "claim": "Acme Transit passes may be cancelled within 45 days of purchase.",
                "source_id": "transit_policy_2024",
            }],
            "metadata": {"case": "constructed-growth-demo", "scenario": "stale-policy"},
        },
        "fixed": {
            "query": "What is the current Acme Transit cancellation window?",
            "answer": "Acme Transit passes may be cancelled within 14 days of purchase.",
            "contexts": [{
                "id": "transit_policy_2026",
                "text": "Acme Transit passes may be cancelled within 14 days of purchase.",
                "metadata": {
                    "source": "transit-cancellations.md", "version": "2026",
                    "source_status": "current", "canonical": True, "authority_score": 1.0,
                },
            }],
            "citations": [{
                "claim": "Acme Transit passes may be cancelled within 14 days of purchase.",
                "source_id": "transit_policy_2026",
            }],
            "metadata": {"case": "constructed-growth-demo", "scenario": "current-policy"},
        },
        "broken_assert": {"summary.source_status": "grounded_but_stale", "summary.supported": 1},
        "fixed_assert": {"summary.source_status": "supported_by_canonical_source", "summary.supported": 1},
        "cause": "The retriever selected an archived but lexically perfect policy, so ordinary groundedness looked healthy.",
        "fix": "Filter inactive documents before ranking and preserve lifecycle metadata on every selected chunk.",
        "guard": "Require a canonical current source for operational queries and keep the broken trace as a source-condition regression.",
    },
    {
        "slug": "misleading-citation",
        "title": "A correct sentence with the wrong citation",
        "question": "How long is the Northstar device warranty?",
        "signal": "citation_mismatch",
        "broken": {
            "query": "How long is the Northstar device warranty?",
            "answer": "Northstar devices include a two-year warranty.",
            "contexts": [
                {"id": "shipping_faq", "text": "Northstar devices ship within two business days.", "metadata": {"source": "shipping.md"}},
                {"id": "warranty_terms", "text": "Northstar devices include a two-year warranty.", "metadata": {"source": "warranty.md", "canonical": True}},
            ],
            "citations": [{"claim": "Northstar devices include a two-year warranty.", "source_id": "shipping_faq"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "wrong-citation"},
        },
        "fixed": {
            "query": "How long is the Northstar device warranty?",
            "answer": "Northstar devices include a two-year warranty.",
            "contexts": [
                {"id": "shipping_faq", "text": "Northstar devices ship within two business days.", "metadata": {"source": "shipping.md"}},
                {"id": "warranty_terms", "text": "Northstar devices include a two-year warranty.", "metadata": {"source": "warranty.md", "canonical": True}},
            ],
            "citations": [{"claim": "Northstar devices include a two-year warranty.", "source_id": "warranty_terms"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "correct-citation"},
        },
        "broken_assert": {"summary.failure_type": "citation_mismatch", "summary.citation_mismatches": 1},
        "fixed_assert": {"summary.failure_type": "no_failure_detected", "summary.citation_mismatches": 0},
        "cause": "The answer generator used the right retrieved fact while the citation renderer attached the first result.",
        "fix": "Bind each emitted claim to the chunk that supports it after answer generation.",
        "guard": "Fail CI when a supported claim cites a different source than its best evidence span.",
    },
    {
        "slug": "conflicting-sources",
        "title": "Two retrieved runbooks disagree",
        "question": "How many reviewers must approve a current Atlas production deploy?",
        "signal": "grounded_but_conflicted",
        "broken": {
            "query": "How many reviewers must approve a current Atlas production deploy?",
            "answer": "An Atlas production deploy requires two reviewers.",
            "contexts": [
                {"id": "deploy_runbook_team", "text": "An Atlas production deploy requires two reviewers.", "metadata": {"source": "team-runbook.md", "source_status": "grounded_but_conflicted", "authority_score": 0.7}},
                {"id": "deploy_runbook_security", "text": "An Atlas production deploy requires three reviewers.", "metadata": {"source": "security-runbook.md", "authority_score": 0.7}},
            ],
            "citations": [{"claim": "An Atlas production deploy requires two reviewers.", "source_id": "deploy_runbook_team"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "conflicting-runbooks"},
        },
        "fixed": {
            "query": "How many reviewers must approve a current Atlas production deploy?",
            "answer": "An Atlas production deploy requires three reviewers.",
            "contexts": [{"id": "deploy_runbook_v2", "text": "An Atlas production deploy requires three reviewers.", "metadata": {"source": "atlas-deploy.md", "version": "2", "canonical": True, "status": "current", "authority_score": 1.0}}],
            "citations": [{"claim": "An Atlas production deploy requires three reviewers.", "source_id": "deploy_runbook_v2"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "resolved-runbook"},
        },
        "broken_assert": {"summary.source_status": "grounded_but_conflicted", "summary.supported": 1},
        "fixed_assert": {"summary.source_status": "supported_by_canonical_source", "summary.supported": 1},
        "cause": "Two teams published contradictory runbooks without canonical ownership or precedence metadata.",
        "fix": "Assign one canonical runbook, retire the competing instruction, and reindex both source records.",
        "guard": "Reject current operational answers while retrieved sources still contain unresolved disagreement.",
    },
    {
        "slug": "evidence-gap",
        "title": "The answer invents a detail absent from retrieval",
        "question": "How long are Bluebird support logs retained?",
        "signal": "unsupported_claim",
        "broken": {
            "query": "How long are Bluebird support logs retained?",
            "answer": "Bluebird support logs are retained for 180 days.",
            "contexts": [{"id": "support_access", "text": "Only the support operations team may access Bluebird support logs.", "metadata": {"source": "support-access.md", "canonical": True}}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "missing-retention-fact"},
        },
        "fixed": {
            "query": "How long are Bluebird support logs retained?",
            "answer": "Bluebird support logs are retained for 90 days.",
            "contexts": [{"id": "retention_policy", "text": "Bluebird support logs are retained for 90 days.", "metadata": {"source": "retention.md", "canonical": True, "status": "current"}}],
            "citations": [{"claim": "Bluebird support logs are retained for 90 days.", "source_id": "retention_policy"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "retrieved-retention-fact"},
        },
        "broken_assert": {"summary.partially_supported": 1, "summary.failure_type": "partial_support"},
        "fixed_assert": {"summary.supported": 1, "summary.should_abstain": False},
        "cause": "Retrieval found a topically related access-control page but no retention duration.",
        "fix": "Route retention questions to the policy namespace and abstain when the duration is absent.",
        "guard": "Keep the missing-evidence trace and require zero unsupported claims before release.",
    },
    {
        "slug": "retrieval-regression",
        "title": "A retriever upgrade removes the only supporting chunk",
        "question": "What is the Vega rollback target?",
        "signal": "regression",
        "broken": {
            "query": "What is the Vega rollback target?",
            "answer": "Vega services should roll back within 20 minutes.",
            "contexts": [{"id": "vega_retention", "text": "Vega deployment records are retained for 90 days.", "metadata": {"source": "vega-records.md"}}],
            "metadata": {"case": "constructed-growth-demo", "retriever": "dense-v2"},
        },
        "fixed": {
            "query": "What is the Vega rollback target?",
            "answer": "Vega services should roll back within 20 minutes.",
            "contexts": [{"id": "vega_rollback", "text": "Vega services should roll back within 20 minutes.", "metadata": {"source": "vega-runbook.md", "canonical": True}}],
            "citations": [{"claim": "Vega services should roll back within 20 minutes.", "source_id": "vega_rollback"}],
            "metadata": {"case": "constructed-growth-demo", "retriever": "hybrid-v1"},
        },
        "broken_assert": {"summary.unsupported": 1, "summary.failure_type": "should_have_abstained"},
        "fixed_assert": {"summary.supported": 1, "summary.failure_type": "no_failure_detected"},
        "cause": "The new embedding model ranked a retention document over the rollback runbook.",
        "fix": "Restore the runbook namespace boost and compare selected context IDs before deployment.",
        "guard": "Use the passing trace as baseline and reject a current trace whose support rate falls.",
    },
    {
        "slug": "ci-debugging-walkthrough",
        "title": "From a failed CI gate to a repaired trace",
        "question": "At what error rate does Nimbus page the on-call engineer?",
        "signal": "contradicted_claim",
        "broken": {
            "query": "At what error rate does Nimbus page the on-call engineer?",
            "answer": "Nimbus pages the on-call engineer when errors exceed 4 percent.",
            "contexts": [{"id": "nimbus_alerts", "text": "Nimbus pages the on-call engineer when errors exceed 2 percent.", "metadata": {"source": "nimbus-alerts.md", "canonical": True, "source_status": "current"}}],
            "citations": [{"claim": "Nimbus pages the on-call engineer when errors exceed 4 percent.", "source_id": "nimbus_alerts"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "ci-failure"},
        },
        "fixed": {
            "query": "At what error rate does Nimbus page the on-call engineer?",
            "answer": "Nimbus pages the on-call engineer when errors exceed 2 percent.",
            "contexts": [{"id": "nimbus_alerts", "text": "Nimbus pages the on-call engineer when errors exceed 2 percent.", "metadata": {"source": "nimbus-alerts.md", "canonical": True, "status": "current"}}],
            "citations": [{"claim": "Nimbus pages the on-call engineer when errors exceed 2 percent.", "source_id": "nimbus_alerts"}],
            "metadata": {"case": "constructed-growth-demo", "scenario": "ci-repaired"},
        },
        "broken_assert": {"summary.contradicted": 1, "claims.0.verdict": "contradicted"},
        "fixed_assert": {"summary.supported": 1, "summary.failure_type": "no_failure_detected"},
        "cause": "A prompt example still contained the retired four-percent threshold.",
        "fix": "Remove the stale prompt fact and generate the value only from the selected runbook span.",
        "guard": "Run the saved trace pair in CI and display the claim, evidence, cause, and fix when it fails.",
    },
]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def case_readme(case: dict) -> str:
    slug = case["slug"]
    return f"""# {case['title']}

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/{slug}/broken.json --json
contexttrace verify examples/investigations/{slug}/fixed.json --json
python examples/investigations/run.py --case {slug}
```

The question is: **{case['question']}** The broken trace is expected to expose `{case['signal']}`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

{case['cause']} The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

{case['fix']} The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

{case['guard']} Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
"""


def build_investigations() -> None:
    for case in CASES:
        directory = INVESTIGATIONS / case["slug"]
        write_json(directory / "broken.json", case["broken"])
        write_json(directory / "fixed.json", case["fixed"])
        write_json(directory / "regression.json", {
            "schema_version": "contexttrace-growth-regression-v1",
            "case_id": case["slug"],
            "construction_status": "constructed_fictional_product_demo",
            "broken_trace": "broken.json",
            "fixed_trace": "fixed.json",
            "broken_assertions": case["broken_assert"],
            "fixed_assertions": case["fixed_assert"],
        })
        (directory / "README.md").write_text(case_readme(case), encoding="utf-8")

    rows = "\n".join(
        f"| [{case['title']}]({case['slug']}/README.md) | `{case['signal']}` | `{case['slug']}` |"
        for case in CASES
    )
    (INVESTIGATIONS / "README.md").write_text(f"""# Six reproducible RAG failure investigations

These public, fictional cases show the full ContextTrace workflow: preserve the broken trace, localize the evidence-chain failure, apply a targeted fix, and keep an executable regression artifact. They are product demonstrations and were not used as final research evaluation cases.

| Investigation | Signal | Runner ID |
| --- | --- | --- |
{rows}

```bash
python examples/investigations/run.py --all
```

Every case runs offline with the stable `semantic_v1_calibrated` verifier. `regression.json` records the exact broken and repaired assertions.
""", encoding="utf-8")


FONT = ImageFont.load_default(size=24)
FONT_SMALL = ImageFont.load_default(size=18)


def terminal_frame(title: str, command: str, lines: list[tuple[str, str]], step: str) -> Image.Image:
    image = Image.new("RGB", (1280, 720), "#08111f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((44, 36, 1236, 684), radius=20, fill="#101b2d", outline="#304260", width=2)
    draw.ellipse((72, 62, 88, 78), fill="#ff5f57")
    draw.ellipse((98, 62, 114, 78), fill="#febc2e")
    draw.ellipse((124, 62, 140, 78), fill="#28c840")
    draw.text((166, 58), "ContextTrace · local demo", font=FONT_SMALL, fill="#93a4bd")
    draw.text((78, 116), title, font=FONT, fill="#f4f7fb")
    draw.text((78, 168), f"$ {command}", font=FONT_SMALL, fill="#67e8f9")
    y = 226
    palette = {"ok": "#86efac", "bad": "#fda4af", "info": "#cbd5e1", "warn": "#fde68a"}
    for kind, line in lines:
        draw.text((78, y), line, font=FONT_SMALL, fill=palette[kind])
        y += 38
    draw.text((78, 638), step, font=FONT_SMALL, fill="#93a4bd")
    return image


def save_demo(name: str, frames: list[Image.Image], durations: list[int]) -> None:
    output = VIDEOS / f"{name}.gif"
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def build_videos() -> None:
    stale_frames = [
        terminal_frame("Catch a stale but grounded answer", "contexttrace verify broken.json", [("ok", "support: supported   citation: citation_ok"), ("bad", "source: grounded_but_stale"), ("warn", "abstain: true   root cause: stale_context")], "1 / 3 · A green groundedness score hides an expired source"),
        terminal_frame("Inspect the evidence chain", "contexttrace diagnose broken.json", [("info", "selected: transit_policy_2024"), ("bad", "metadata.status: stale"), ("info", "suggested fix: retrieve the current canonical policy")], "2 / 3 · The trace points to the source lifecycle failure"),
        terminal_frame("Verify the repair", "contexttrace verify fixed.json", [("ok", "support: supported   citation: citation_ok"), ("ok", "source: supported_by_canonical_source"), ("ok", "regression assertions: PASS")], "3 / 3 · The repaired trace becomes an executable guard"),
    ]
    save_demo("stale-source-to-regression", stale_frames, [4200, 4200, 5200])

    citation_frames = [
        terminal_frame("Debug a misleading citation", "contexttrace verify broken.json", [("ok", "claim: supported"), ("bad", "citation: claim_supported_by_different_source"), ("bad", "root cause: wrong_source_cited")], "1 / 3 · The sentence is right, but the cited chunk is not"),
        terminal_frame("Apply the claim-level fix", "python examples/investigations/run.py --case misleading-citation", [("info", "broken source: shipping_faq"), ("info", "supporting source: warranty_terms"), ("ok", "fixed citation: warranty_terms")], "2 / 3 · Bind the claim to its actual evidence span"),
        terminal_frame("Gate the behavior in CI", "python examples/investigations/run.py --all", [("ok", "6 investigations passed"), ("ok", "12 traces verified"), ("ok", "0 assertion failures")], "3 / 3 · One offline command protects the full set"),
    ]
    save_demo("citation-failure-to-ci", citation_frames, [4200, 4200, 5200])

    (VIDEOS / "stale-source-to-regression.vtt").write_text("""WEBVTT

00:00.000 --> 00:04.200
A grounded answer can still rely on an expired source.

00:04.200 --> 00:08.400
ContextTrace identifies the stale selected policy and suggests retrieving the current canonical source.

00:08.400 --> 00:13.600
The repaired trace passes support, citation, source-condition, and regression checks.
""", encoding="utf-8")
    (VIDEOS / "citation-failure-to-ci.vtt").write_text("""WEBVTT

00:00.000 --> 00:04.200
The answer is supported, but its citation points to an unrelated shipping page.

00:04.200 --> 00:08.400
The fix binds the claim to the warranty source that actually supports it.

00:08.400 --> 00:13.600
The offline investigation runner checks all six saved regressions in CI.
""", encoding="utf-8")
    (VIDEOS / "requirements.txt").write_text("Pillow==12.3.0\n", encoding="utf-8")
    (VIDEOS / "README.md").write_text("""# Reproducible demo videos

These two silent animated terminal demos are generated from scripted frames and ship with WebVTT captions. Each is 1280×720, 13.6 seconds, loops continuously, and uses the same public fictional cases as the investigation runner.

| Demo | Video | Captions | Story |
| --- | --- | --- | --- |
| Stale source to regression | [GIF](stale-source-to-regression.gif) | [WebVTT](stale-source-to-regression.vtt) | Supported answer → stale source → canonical repair |
| Citation failure to CI | [GIF](citation-failure-to-ci.gif) | [WebVTT](citation-failure-to-ci.vtt) | Supported claim → wrong citation → six-case gate |

Rebuild them after installing the development dependencies:

```bash
python -m pip install -r docs/assets/demos/requirements.txt
python scripts/build_growth_assets.py
```

The GIF format makes the clips playable in GitHub, package documentation, and social posts without an external host. Captions contain the complete narration for accessibility and adaptation.
""", encoding="utf-8")


def main() -> None:
    build_investigations()
    build_videos()
    outputs = sorted(
        [path for path in INVESTIGATIONS.rglob("*") if path.is_file()]
        + [path for path in VIDEOS.rglob("*") if path.is_file()]
    )
    manifest = {
        "schema_version": "contexttrace-growth-build-v1",
        "investigation_count": len(CASES),
        "video_count": 2,
        "files": [
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in outputs
        ],
    }
    write_json(ROOT / "research" / "solo_regression_2026" / "GROWTH_ASSETS_BUILD.json", manifest)
    print(f"Built {len(CASES)} investigations and 2 animated demos ({len(outputs)} files).")


if __name__ == "__main__":
    main()
