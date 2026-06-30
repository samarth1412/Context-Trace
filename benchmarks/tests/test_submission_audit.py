from pathlib import Path

from paper.audit_submission import _heading_page, audit_anonymity


def test_heading_page_handles_acl_line_and_section_numbers() -> None:
    pages = ["1 Introduction\n", "428   12   Limitations        other column\n", "497 References\n"]

    assert _heading_page(pages, "Limitations") == 2
    assert _heading_page(pages, "References") == 3


def test_anonymity_audit_fails_on_paper_identity(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text("Author: " + "sam" + "arth", encoding="utf-8")

    report = audit_anonymity([paper])

    assert report["status"] == "failed"
    assert report["blocking_finding_count"] == 1
    assert report["findings"][0]["classification"] == "release_surface"


def test_anonymity_audit_quarantines_nonrelease_dataset_occurrence(tmp_path: Path) -> None:
    output = tmp_path / "benchmarks" / "contexttrace_bench" / "out" / "legacy"
    output.mkdir(parents=True)
    (output / "third_party.json").write_text("contact@example.com", encoding="utf-8")

    report = audit_anonymity([tmp_path / "benchmarks" / "contexttrace_bench" / "out"])

    assert report["status"] == "passed"
    assert report["blocking_finding_count"] == 0
    assert report["quarantined_nonrelease_count"] == 1
