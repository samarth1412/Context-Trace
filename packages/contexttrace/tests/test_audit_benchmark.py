import json

from contexttrace.cli import main
from contexttrace.verify.audit_benchmark import (
    run_audit_benchmark,
    write_audit_benchmark_report,
)


def test_audit_benchmark_scores_real_oss_cases():
    result = run_audit_benchmark(mode="semantic", case_set="real")

    assert result["mode"] == "semantic"
    assert result["case_set"] == "real"
    assert result["case_source"] == "real OSS RAG docs, public GitHub issue snippets, and ContextTrace docs"
    assert result["cases"] >= 20
    assert result["exact_match_rate"] >= 0.9
    assert set(result["per_label"]) >= {
        "answer_overreach",
        "chunking_issue",
        "corpus_gap",
        "insufficient_context",
        "no_failure_detected",
        "reranking_failure",
        "retrieval_miss",
        "stale_source",
    }
    assert any("qdrant.tech" in row["source"] for row in result["rows"])
    assert any("github.com/chroma-core" in row["source"] for row in result["rows"])
    assert any("docs.haystack" in row["source"] for row in result["rows"])
    assert any("langchain" in row["source"] for row in result["rows"])


def test_audit_benchmark_cli_json(capsys):
    assert main(["audit-benchmark", "--mode", "semantic", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "semantic"
    assert output["cases"] >= 20
    assert output["exact_match_rate"] >= 0.9
    assert output["per_label"]["retrieval_miss"]["recall"] >= 0.9


def test_audit_benchmark_cli_report(tmp_path, capsys):
    report_path = tmp_path / "audit_benchmark.html"

    assert main(["audit-benchmark", "--mode", "semantic", "--report", "--out", str(report_path)]) == 0

    output = capsys.readouterr().out
    assert "Case source: real OSS RAG docs, public GitHub issue snippets, and ContextTrace docs" in output
    assert "Report: %s" % report_path in output
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Audit Benchmark" in html
    assert "Usefulness Summary" in html
    assert "Audit Label Metrics" in html
    assert "Misses To Inspect" in html


def test_audit_benchmark_report_generation(tmp_path):
    result = run_audit_benchmark(mode="semantic", case_set="real")
    report_path = tmp_path / "audit_benchmark.html"

    written = write_audit_benchmark_report(result, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "Raw JSON" in html
    assert "retrieval_miss" in html
