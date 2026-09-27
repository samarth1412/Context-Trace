"""Score a V10 split with frozen local group and evidence-span models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.requirement_alignment.score_v6_cascade import score_local_models
from benchmarks.requirement_alignment.score_v9_auxiliary import score_auxiliary


SPLITS = (
    "climate_fever_v10_training",
    "climate_fever_v10_development",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", required=True, choices=SPLITS)
    parser.add_argument("--v3-model-path", required=True)
    parser.add_argument("--v3-manifest", required=True)
    parser.add_argument("--v5-model-path", required=True)
    parser.add_argument("--v5-manifest", required=True)
    parser.add_argument("--pinned-nli-path", required=True)
    parser.add_argument("--local-output", required=True)
    parser.add_argument("--auxiliary-output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    common = {
        "expected_split": args.split,
        "v3_model_path": args.v3_model_path,
        "v3_manifest_path": args.v3_manifest,
        "v5_model_path": args.v5_model_path,
        "v5_manifest_path": args.v5_manifest,
        "batch_size": args.batch_size,
    }
    local = score_local_models(args.dataset, **common)
    auxiliary = score_auxiliary(
        args.dataset, pinned_nli_path=args.pinned_nli_path, **common
    )
    for path, value in (
        (Path(args.local_output), local),
        (Path(args.auxiliary_output), auxiliary),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "split": args.split,
                "cases": local["cases"],
                "remote_inference_used": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
