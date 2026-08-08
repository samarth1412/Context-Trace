import json

from benchmarks.contexttrace_unseen_v2.freeze_candidate import (
    MAX_IDENTIFIER_SCOPE_TERMS,
    MAX_SCOPE_SEPARATORS,
    METRICS,
    TAXONOMY_VERSION,
    _canonical_sha256,
    _source_rows,
)


def test_unseen_v2_metrics_are_strict_and_clustered() -> None:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))

    assert metrics["statistics"]["bootstrap"]["cluster_key"] == "source_family"
    assert metrics["statistics"]["bootstrap"]["replicates"] == 10000
    assert metrics["statistics"]["paired_randomization"]["replicates"] == 100000
    assert (
        metrics["sota_candidate_gates"]["dangerous_false_green_rate"]["value"] == 0.01
    )
    assert (
        metrics["sota_candidate_gates"]["physical_nli_invocation_rate"]["value"] == 0.4
    )


def test_candidate_source_manifest_is_sorted_and_hashable() -> None:
    rows = _source_rows()
    paths = {row["path"] for row in rows}

    assert rows == sorted(rows, key=lambda row: row["path"])
    assert all(row["bytes"] > 0 for row in rows)
    assert len(_canonical_sha256(rows)) == 64
    assert "packages/contexttrace/contexttrace/verify/facts.py" in paths
    assert "packages/contexttrace/contexttrace/verify/claims.py" in paths
    assert "packages/contexttrace/contexttrace/verify/judges.py" in paths
    assert "benchmarks/contexttrace_unseen_v2/METRICS.json" in paths


def test_freeze_uses_semantic_v2_taxonomy() -> None:
    assert TAXONOMY_VERSION == "contexttrace-diagnosis-v2.0"
    assert MAX_IDENTIFIER_SCOPE_TERMS == 8
    assert MAX_SCOPE_SEPARATORS == 12
