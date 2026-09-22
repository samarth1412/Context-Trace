"""Acquire the exact public source files for the five-way confirmation set."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


SOURCES = {
    "wice_test.jsonl": {
        "url": (
            "https://raw.githubusercontent.com/ryokamoi/wice/"
            "ddeb6c183665e2a20c5f03c5aa07f03888b9870f/"
            "data/entailment_retrieval/claim/test.jsonl"
        ),
        "sha256": "4c91b9e9590cfcd8f8a0f7288b5ff315af8ade946d7bf26f50fbd671bb86dbe8",
    },
    "ambient_test.jsonl": {
        "url": (
            "https://raw.githubusercontent.com/alisawuffles/ambient/"
            "1fcb43effda068f3047d46b6f9ff0e50e0ee1c1b/"
            "AmbiEnt/test.jsonl"
        ),
        "sha256": "f31fa1f24307ae6c4b4b25da1c0aae2193ccbe14252928c279fc909c950540df",
    },
    "vitaminc.zip": {
        "url": "https://github.com/TalSchuster/talschuster.github.io/raw/master/static/vitaminc.zip",
        "sha256": "49d82dc1690cbee420d18e2c26f687a7937710bb211845d2571430dfd4dc0337",
    },
}


class AcquisitionError(RuntimeError):
    """Raised when a public source cannot be acquired exactly."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire(output_dir: str | Path) -> dict[str, object]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, source in SOURCES.items():
        destination = target / name
        if not destination.exists() or sha256(destination) != source["sha256"]:
            with urllib.request.urlopen(str(source["url"]), timeout=120) as response:  # noqa: S310
                destination.write_bytes(response.read())
        actual = sha256(destination)
        if actual != source["sha256"]:
            raise AcquisitionError(
                "%s has sha256 %s; expected %s" % (destination, actual, source["sha256"])
            )
        rows.append(
            {
                "name": name,
                "path": str(destination),
                "url": source["url"],
                "sha256": actual,
                "bytes": destination.stat().st_size,
            }
        )
    return {"sources": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(acquire(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
