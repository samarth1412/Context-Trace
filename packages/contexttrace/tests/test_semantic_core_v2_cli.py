from __future__ import annotations

import json

from contexttrace.cli import main


def _write_trace(tmp_path, *, contexts=None):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "query": "What is the refund window?",
                "answer": "The refund window is 14 days.",
                "contexts": contexts
                if contexts is not None
                else [
                    {
                        "id": "refunds",
                        "text": "The refund window is 14 days.",
                        "metadata": {"canonical": True, "current": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_verify_v2_is_explicit_and_deterministic_by_default(tmp_path, capsys) -> None:
    trace_path = _write_trace(tmp_path)

    assert main(["verify-v2", str(trace_path), "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["profile_id"] == "deterministic_only_v2_1_safety"
    assert result["summary"]["overall_status"] == "green"
    assert result["summary"]["nli_invocations"] == 0


def test_verify_v2_can_write_result_and_enforce_status(tmp_path, capsys) -> None:
    trace_path = _write_trace(tmp_path, contexts=[])
    output_path = tmp_path / "result.json"

    assert (
        main(
            [
                "verify-v2",
                str(trace_path),
                "--output",
                str(output_path),
                "--fail-on",
                "abstained",
            ]
        )
        == 1
    )

    assert output_path.exists()
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["summary"]["overall_status"] == "abstained"
    assert "Result:" in capsys.readouterr().out


def test_verify_v2_selective_requires_pinned_local_model(tmp_path, capsys) -> None:
    trace_path = _write_trace(tmp_path)

    assert main(["verify-v2", str(trace_path), "--profile", "selective"]) == 1

    assert "--model-path" in capsys.readouterr().err
