from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_bench.author_audit import build_author_audit_packet


def _packet() -> dict:
    return {
        "schema_version": 1,
        "dataset": "test-set",
        "case_count": 1,
        "reviewer": "",
        "review_kind": "",
        "cases": [
            {
                "blind_id": "ARR-0001",
                "input": {"query": "Q", "answer": "A", "contexts": []},
                "annotation": {},
            }
        ],
    }


def test_build_author_audit_is_blinded_and_pending(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(_packet()), encoding="utf-8")

    result = build_author_audit_packet(packet_path=packet_path, output_dir=tmp_path / "audit")
    output = Path(result["output_dir"])
    row = json.loads((output / "audit_packet.jsonl").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

    assert row["blind_id"] == "ARR-0001"
    assert "expected" not in json.dumps(row).lower()
    assert "predicted" not in json.dumps(row).lower()
    assert summary["status"] == "pending_author_completion"
    assert summary["independent"] is False
    assert summary["paper_result_eligible"] is False
    assert (output / "responses.jsonl").read_text(encoding="utf-8") == ""
    assert (output / "disagreements.jsonl").read_text(encoding="utf-8") == ""
    assert (output / "corrections.jsonl").read_text(encoding="utf-8") == ""


def test_build_author_audit_rejects_hidden_labels(tmp_path: Path) -> None:
    packet = _packet()
    packet["cases"][0]["expected"] = ["unsupported_answer"]
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    with pytest.raises(ValueError, match="blinded validation|forbidden"):
        build_author_audit_packet(packet_path=packet_path, output_dir=tmp_path / "audit")
