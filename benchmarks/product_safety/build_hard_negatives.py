"""Build the deterministic checker-development hard-negative corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_SEEDS = HERE / "hard_negative_seeds.json"
DEFAULT_OUTPUT = HERE / "hard_negative_cases.json"
BUILDER_VERSION = "contexttrace-hard-negative-builder-v1.0.0"


def build_corpus(seed_path: Path = DEFAULT_SEEDS) -> dict[str, Any]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    seeds = list(payload.get("seeds") or [])
    cases: list[dict[str, Any]] = []
    for seed in seeds:
        seed_id = _required(seed, "id")
        category = _required(seed, "category")
        supported = _required(seed, "supported_claim")
        premise = _required(seed, "premise")
        mutation = dict(seed.get("replace") or {})
        old = _required(mutation, "old")
        if "new" not in mutation or not isinstance(mutation["new"], str):
            raise ValueError(f"{seed_id} mutation target must be a string.")
        new = mutation["new"]
        if supported.count(old) != 1:
            raise ValueError(f"{seed_id} must contain mutation source exactly once.")
        if new and new in premise:
            raise ValueError(f"{seed_id} mutation target already appears in premise.")
        negative = supported.replace(old, new, 1)
        common = {
            "seed_id": seed_id,
            "category": category,
            "query": _required(seed, "query"),
            "premise": premise,
            "source_kind": "deterministic_seed_mutation",
        }
        cases.extend(
            [
                {
                    **common,
                    "id": f"{seed_id}__positive",
                    "claim": supported,
                    "expected": "supported",
                    "mutation": None,
                },
                {
                    **common,
                    "id": f"{seed_id}__hard_negative",
                    "claim": negative,
                    "expected": "not_supported",
                    "mutation": {"old": old, "new": new},
                },
            ]
        )

    corpus: dict[str, Any] = {
        "schema_version": "1.0",
        "builder_version": BUILDER_VERSION,
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "seed_sha256": _sha256_bytes(seed_path.read_bytes()),
        "case_count": len(cases),
        "cases": cases,
    }
    corpus["payload_sha256"] = _canonical_sha256(corpus)
    return corpus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(build_corpus(args.seeds), indent=2, sort_keys=True) + "\n"
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != rendered
        ):
            raise SystemExit("Hard-negative corpus is missing or stale.")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    return 0


def _required(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required value: {key}.")
    return value


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(raw)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
