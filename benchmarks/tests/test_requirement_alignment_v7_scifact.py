from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.requirement_alignment import build_v7_scifact
from benchmarks.requirement_alignment.build_v7_scifact import build
from benchmarks.requirement_alignment.v7_scifact import evaluate_transfer


ROOT = Path(__file__).resolve().parents[2]
V7 = ROOT / "benchmarks" / "requirement_alignment"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_scifact_builder_freezes_disjoint_balanced_splits(tmp_path, monkeypatch) -> None:
    source = tmp_path / "data"
    source.mkdir()
    archive = tmp_path / "data.tar.gz"
    archive.write_bytes(b"frozen-scifact-fixture")
    monkeypatch.setattr(
        build_v7_scifact,
        "ARCHIVE_SHA256",
        hashlib.sha256(archive.read_bytes()).hexdigest(),
    )
    _write_jsonl(
        source / "corpus.jsonl",
        [
            {
                "doc_id": 1,
                "title": "support",
                "abstract": ["Treatment lowers risk.", "Background sentence."],
                "structured": False,
            },
            {
                "doc_id": 2,
                "title": "conflict",
                "abstract": ["Treatment raises risk."],
                "structured": False,
            },
            {
                "doc_id": 3,
                "title": "missing",
                "abstract": ["Risk was measured.", "No treatment comparison was reported."],
                "structured": False,
            },
        ],
    )

    def claims(offset: int) -> list[dict[str, object]]:
        return [
            {
                "id": offset + 1,
                "claim": "Treatment lowers risk.",
                "evidence": {"1": [{"label": "SUPPORT", "sentences": [0]}]},
                "cited_doc_ids": [1],
            },
            {
                "id": offset + 2,
                "claim": "Treatment lowers risk.",
                "evidence": {"2": [{"label": "CONTRADICT", "sentences": [0]}]},
                "cited_doc_ids": [2],
            },
            {
                "id": offset + 3,
                "claim": "Treatment lowers risk.",
                "evidence": {},
                "cited_doc_ids": [3],
            },
        ]

    _write_jsonl(source / "claims_train.jsonl", claims(0))
    _write_jsonl(source / "claims_dev.jsonl", claims(100))
    development, evaluation, audit, manifest = build(
        source,
        source_archive=archive,
        development_per_relation=1,
        evaluation_per_relation=1,
    )
    assert len(development["examples"]) == 3
    assert len(evaluation["examples"]) == 3
    assert audit["development"]["relations"] == {
        "Contradiction": 1,
        "Entailment": 1,
        "NotMentioned": 1,
    }
    assert audit["checks"]["claim_ids_disjoint"] is True
    assert audit["checks"]["labels_absent_from_inputs"] is True
    assert audit["checks"]["synthetic_labels_used"] is False
    assert manifest["status"] == "frozen_before_model_scoring"
    assert manifest["policy_selection_uses_scifact"] is False
    for row in development["examples"] + evaluation["examples"]:
        assert not ({"label", "target", "relation"} & set(row["input"]))


def test_transfer_evaluation_attributes_routed_support(tmp_path) -> None:
    policy = {
        "local_missing_threshold": 0.5,
        "local_supported_threshold": 0.8,
        "jev_supported_probability": 0.5,
        "review_confidence": 0.8,
        "always_review_supported": True,
    }
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    policy_payload = {
        "schema_version": "contexttrace-requirement-v6-cascade-policy-1.0",
        "selection_split": "cascade_calibration",
        "evaluation_used_for_selection": False,
        "policy_id": hashlib.sha256(encoded).hexdigest(),
        "policy": policy,
    }
    relations = ("Entailment", "Contradiction", "NotMentioned")
    dataset = {
        "examples": [
            {
                "id": relation.lower(),
                "split": "scifact_evaluation",
                "target": {"label": "covered" if relation == "Entailment" else "missing"},
                "source": {"relation": relation},
            }
            for relation in relations
        ]
    }
    local = {
        "split": "scifact_evaluation",
        "rows": [
            {
                "case_id": "entailment",
                "predictions": {
                    "v3": {"entailment_probability": 0.7},
                    "v5": {"entailment_probability": 0.7},
                },
            },
            {
                "case_id": "contradiction",
                "predictions": {
                    "v3": {"entailment_probability": 0.1},
                    "v5": {"entailment_probability": 0.2},
                },
            },
            {
                "case_id": "notmentioned",
                "predictions": {
                    "v3": {"entailment_probability": 0.6},
                    "v5": {"entailment_probability": 0.6},
                },
            },
        ],
    }

    def prediction(verdict: str, supported: float) -> dict[str, object]:
        return {
            "verdict": verdict,
            "probabilities": {"supported": supported},
            "confidence": 0.9,
            "latency_ms": 10.0,
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        }

    jev = {
        "split": "scifact_evaluation",
        "complete": True,
        "rows": [
            {"case_id": "entailment", "prediction": prediction("supported", 0.9)},
            {"case_id": "notmentioned", "prediction": prediction("unsupported", 0.0)},
        ],
    }
    paths = {}
    for name, payload in (
        ("dataset", dataset),
        ("local", local),
        ("jev", jev),
        ("policy", policy_payload),
    ):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    result = evaluate_transfer(
        paths["dataset"], paths["local"], paths["jev"], paths["policy"]
    )
    assert result["optional_jev"]["metrics"]["accuracy"] == 1.0
    assert result["optional_jev"]["metrics"]["false_positive_rate"] == 0.0
    assert result["optional_jev"]["operations"]["remote_calls"] == 2
    assert result["local_only"]["network_calls"] == 0
    assert result["transfer_gates"]["absolute_gates_met"] is True
    assert result["stable_defaults_changed"] is False


def test_committed_scifact_transfer_artifacts_are_self_consistent() -> None:
    development = json.loads((V7 / "v7_scifact_development.json").read_text())
    evaluation = json.loads((V7 / "v7_scifact_evaluation.json").read_text())
    audit = json.loads((V7 / "v7_scifact_audit.json").read_text())
    manifest = json.loads((V7 / "v7_scifact_manifest.json").read_text())
    result = json.loads(
        (V7 / "results" / "v7_scifact_evaluation.json").read_text()
    )

    def canonical_sha256(value: object) -> str:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    assert manifest["development_sha256"] == canonical_sha256(development)
    assert manifest["evaluation_sha256"] == canonical_sha256(evaluation)
    assert manifest["audit_sha256"] == canonical_sha256(audit)
    assert len(development["examples"]) == 270
    assert len(evaluation["examples"]) == 180
    assert audit["evaluation"]["relations"] == {
        "Contradiction": 60,
        "Entailment": 60,
        "NotMentioned": 60,
    }
    assert result["policy_selection_uses_scifact"] is False
    assert result["evaluation_used_for_selection"] is False
    assert result["stable_defaults_changed"] is False


def test_committed_jev_rows_reconstruct_minimized_remote_state() -> None:
    dataset = json.loads((V7 / "v7_scifact_evaluation.json").read_text())
    jev = json.loads(
        (V7 / "results" / "v7_scifact_evaluation_jev.json").read_text()
    )
    examples = {row["id"]: row for row in dataset["examples"]}
    assert jev["complete"] is True
    assert jev["completed"] == 124
    assert set(jev["routed_case_ids"]) == {row["case_id"] for row in jev["rows"]}
    for row in jev["rows"]:
        example = examples[row["case_id"]]
        state = {
            "claim": str(example["input"]["claim"]),
            "selected_evidence": [
                {"id": str(item["id"]), "text": str(item["text"])}
                for item in example["input"]["evidence"]
            ],
        }
        encoded = json.dumps(
            state, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        prediction = row["prediction"]
        assert prediction["input_audit"]["state_sha256"] == hashlib.sha256(
            encoded
        ).hexdigest()
        assert prediction["input_audit"]["sent_fields"] == [
            "claim",
            "selected_evidence",
        ]
        assert prediction["input_audit"]["evaluation_label_sent"] is False
        assert set(prediction["probabilities"]) == {
            "supported",
            "partially_supported",
            "unsupported",
            "contradicted",
            "unverifiable",
        }
        assert prediction["reason"] is None
        assert prediction["matched_facts"] == []
        assert prediction["missing_facts"] == []
        assert prediction["conflicting_facts"] == []
