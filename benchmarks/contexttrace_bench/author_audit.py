from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from benchmarks.contexttrace_bench.arr_annotation import (
        REVIEW_PACKET_FORBIDDEN_KEYS,
        validate_blinded_packet,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from arr_annotation import REVIEW_PACKET_FORBIDDEN_KEYS, validate_blinded_packet  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "author_audit"


def build_author_audit_packet(
    *, packet_path: str | Path, output_dir: str | Path = DEFAULT_OUTPUT_DIR
) -> dict[str, Any]:
    source_path = Path(packet_path)
    packet = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ValueError("Annotation packet must be a JSON object.")
    validation = validate_blinded_packet(packet)
    if validation["status"] != "passed":
        raise ValueError("Annotation packet failed blinded validation: %s" % validation["errors"])
    if str(packet.get("reviewer") or "").strip() or str(packet.get("review_kind") or "").strip():
        raise ValueError("Author-audit source must be an unassigned blank packet.")

    rows = list(packet["cases"])
    leaked = sorted(_find_forbidden_keys(rows))
    if leaked:
        raise ValueError("Author-audit packet contains forbidden fields: %s" % leaked)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    audit_path = destination / "audit_packet.jsonl"
    audit_payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    audit_path.write_text(audit_payload, encoding="utf-8")

    ledger_paths = {}
    for name in ("responses.jsonl", "disagreements.jsonl", "corrections.jsonl"):
        path = destination / name
        path.write_text("", encoding="utf-8")
        ledger_paths[name] = path

    summary = {
        "schema_version": 1,
        "audit_kind": "blinded_author_fallback",
        "status": "pending_author_completion",
        "independent": False,
        "paper_result_eligible": False,
        "broad_sota_gate_eligible": False,
        "dataset": packet.get("dataset"),
        "case_count": len(rows),
        "completed_responses": 0,
        "disagreements": 0,
        "corrections": 0,
        "source_packet_sha256": _sha256_file(source_path),
        "audit_packet_sha256": _sha256_file(audit_path),
        "validation_status": validation["status"],
        "required_next_step": (
            "Complete blinded judgments, preserve raw responses, then score disagreements "
            "against the private key. Independent review is still required."
        ),
        "files": {
            "audit_packet": audit_path.name,
            "responses": ledger_paths["responses.jsonl"].name,
            "disagreements": ledger_paths["disagreements.jsonl"].name,
            "corrections": ledger_paths["corrections.jsonl"].name,
        },
    }
    summary_path = destination / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": str(destination), "summary": summary}


def _find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in REVIEW_PACKET_FORBIDDEN_KEYS:
                found.add(key)
            found.update(_find_forbidden_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_find_forbidden_keys(nested))
    return found


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an honest blinded author-audit fallback packet.")
    parser.add_argument("--packet", required=True, help="Blank blinded annotation_packet.json.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    result = build_author_audit_packet(packet_path=args.packet, output_dir=args.output_dir)
    print("Author audit status: %s" % result["summary"]["status"])
    print("Cases: %s" % result["summary"]["case_count"])
    print("Output: %s" % result["output_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
