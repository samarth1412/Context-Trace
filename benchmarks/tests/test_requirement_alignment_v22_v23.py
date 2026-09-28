from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "requirement_alignment"


def _result(name: str) -> dict[str, object]:
    return json.loads((BENCHMARK / "results" / name).read_text())


def test_v22_records_the_rejected_domain_candidate() -> None:
    result = _result("v22_domain_candidate.json")
    direct = result["selected"]["direct"]
    policy = result["selected"]["policy"]["metrics"]

    assert result["status"] == "rejected_development_candidate"
    assert result["decision"] == "do_not_promote_v22"
    assert direct["accuracy"] == 0.414
    assert direct["macro_f1"] == 0.4104
    assert policy["support_recall"] == 0.0
    assert policy["false_support_rate"] == 0.0
    assert policy["partial_or_ambiguous_review_recall"] == 0.735
    assert policy["gates"]["all_met"] is False


def test_v23_improves_direct_metrics_but_fails_safe_support() -> None:
    relation = _result("v23_stronger_nli_screen.json")
    atomic = _result("v23_stronger_nli_atomic_screen.json")

    assert relation["decision"] == "do_not_promote_v23"
    assert relation["selected"]["direct"]["accuracy"] == 0.444
    assert relation["selected"]["direct"]["macro_f1"] == 0.4275
    assert relation["selected"]["policy"]["metrics"]["support_recall"] == 0.02
    assert relation["selected"]["policy"]["metrics"]["false_support_rate"] == 0.0
    assert atomic["decision"] == "do_not_promote_v23"
    assert atomic["selected"]["direct"]["accuracy"] == 0.454
    assert atomic["selected"]["direct"]["macro_f1"] == 0.4402
    assert atomic["selected"]["policy"]["metrics"]["support_recall"] == 0.01
    assert atomic["selected"]["policy"]["metrics"]["gates"]["all_met"] is False


def test_v22_v23_artifacts_preserve_privacy_and_defaults() -> None:
    results = [
        _result("v22_domain_candidate.json"),
        _result("v23_stronger_nli_screen.json"),
        _result("v23_stronger_nli_atomic_screen.json"),
    ]

    for result in results:
        assert result["protocol"]["evaluation_labels_in_model_features"] is False
        assert result["protocol"]["dataset_identity_in_model_features"] is False
        assert result["remote_inference_used"] is False
        assert result["local_only_network_calls"] == 0
        assert result["remote_provider_default_enabled"] is False
        assert result["stable_defaults_changed"] is False
        assert all("claim" not in row and "evidence" not in row for row in result["rows"])


def test_v23_manifest_pins_the_local_checkpoint() -> None:
    manifest = _result("v23_stronger_nli_manifest.json")

    assert manifest["model_id"] == (
        "4c94466fb55da3fc09e5cb48b4c7da3303008ac8903b9400f55d4eabd46f24f6"
    )
    assert manifest["revision"] == "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
    assert manifest["license"] == "mit"
    assert manifest["runtime_network_required"] is False
    assert manifest["stable_defaults_changed"] is False
    assert len(manifest["files"]) == 6
