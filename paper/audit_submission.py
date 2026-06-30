from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = Path(__file__).resolve().parent
DEFAULT_PDF = PAPER_DIR / "build" / "main.pdf"
DEFAULT_PAGE_REPORT = PAPER_DIR / "PAGE_LIMIT_AUDIT.md"
DEFAULT_ANONYMITY_REPORT = PAPER_DIR / "ANONYMITY_AUDIT.md"
TEXT_SUFFIXES = {
    ".bib",
    ".csv",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".rst",
    ".sty",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_NAMES = {
    "ANONYMITY_AUDIT.md",
    "audit_submission.py",
}

AUTHOR_NAME = "sam" + "arth"
AUTHOR_HANDLE = AUTHOR_NAME + "1412"
AUTHOR_HANDLE_ALT = AUTHOR_NAME + "vinayaka"
LOCAL_USERNAME = "ma" + "nnv"
GMAIL = "gma" + "il"
UFL = "uf" + "l"
UNIVERSITY = "University" + " of Florida"
PROJECT_URL = "github.com/" + AUTHOR_HANDLE + "/Context-Trace"

IDENTITY_PATTERNS = {
    "author_name": re.compile(r"\b" + re.escape(AUTHOR_NAME) + r"\b", re.IGNORECASE),
    "author_handle": re.compile(re.escape(AUTHOR_HANDLE), re.IGNORECASE),
    "author_handle_alt": re.compile(re.escape(AUTHOR_HANDLE_ALT), re.IGNORECASE),
    "local_username": re.compile(r"\b" + re.escape(LOCAL_USERNAME) + r"\b", re.IGNORECASE),
    "gmail": re.compile(re.escape(GMAIL), re.IGNORECASE),
    "ufl": re.compile(r"\b" + re.escape(UFL) + r"\b", re.IGNORECASE),
    "university_affiliation": re.compile(re.escape(UNIVERSITY), re.IGNORECASE),
    "project_repository": re.compile(re.escape(PROJECT_URL), re.IGNORECASE),
    "project_release_url": re.compile(re.escape(PROJECT_URL) + r"/releases?", re.IGNORECASE),
    "identifiable_pypi": re.compile(r"pypi\.org/project/contexttrace", re.IGNORECASE),
    "personal_site": re.compile(
        r"(?:linkedin\.com/in/|about\.me/|" + re.escape(AUTHOR_NAME) + r"[^\s/]*\.github\.io)",
        re.IGNORECASE,
    ),
    "acknowledgment": re.compile(r"^\s*(?:#+|\\section\*?\{)?acknowledg(?:e)?ments?", re.IGNORECASE | re.MULTILINE),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "windows_user_path": re.compile(r"[A-Z]:\\Users\\[^\\]+\\", re.IGNORECASE),
    "posix_user_path": re.compile(r"/(?:Users|home)/[^/]+/", re.IGNORECASE),
}


def audit_page_limit(pdf_path: str | Path = DEFAULT_PDF) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError("Paper PDF is missing: %s" % path)
    info = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, encoding="utf-8", errors="replace", check=True
    ).stdout
    pages_match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if pages_match is None:
        raise ValueError("pdfinfo did not report a page count.")
    total_pages = int(pages_match.group(1))
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    pages = [page for page in text.split("\f") if page.strip()]
    reference_page = _heading_page(pages, "References")
    limitation_page = _heading_page(pages, "Limitations")
    ethics_page = _heading_page(pages, "Ethics Statement")
    appendix_page = _heading_page(pages, "Appendix")
    content_pages = reference_page if reference_page is not None else total_pages
    reference_pages = total_pages - reference_page + 1 if reference_page is not None else 0
    appendix_pages = total_pages - appendix_page + 1 if appendix_page is not None else 0
    return {
        "pdf": _portable(path),
        "total_pages": total_pages,
        "content_pages_conservative": content_pages,
        "references_start_page": reference_page,
        "reference_pages": reference_pages,
        "limitations_page": limitation_page,
        "ethics_page": ethics_page,
        "appendix_pages": appendix_pages,
        "arr_long_content_limit": 8,
        "fits_arr_long_limit": content_pages <= 8,
        "notes": [
            "Content count is conservative because floats before the References heading share its page.",
            "Large result tables occupy most of pages 5--7; move detailed ablations or error clusters to the appendix if prose expands.",
            "Recheck pagination against the official style revision immediately before submission.",
        ],
    }


def render_page_audit(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Page-limit audit",
            "",
            "- PDF: `%s`" % report["pdf"],
            "- Total pages: `%s`" % report["total_pages"],
            "- Conservative content pages: `%s/%s`"
            % (report["content_pages_conservative"], report["arr_long_content_limit"]),
            "- References start: page `%s`" % report["references_start_page"],
            "- Reference pages: `%s`" % report["reference_pages"],
            "- Limitations: page `%s`" % report["limitations_page"],
            "- Ethics: page `%s`" % report["ethics_page"],
            "- Appendix pages: `%s`" % report["appendix_pages"],
            "- Fits ARR long-paper content limit: `%s`" % report["fits_arr_long_limit"],
            "",
            "## Compression risks",
            "",
            *("- %s" % note for note in report["notes"]),
            "",
        ]
    )


def audit_anonymity(roots: list[str | Path]) -> dict[str, Any]:
    findings = []
    scanned = 0
    for root_value in roots:
        root = Path(root_value)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in paths:
            if path.name in EXCLUDED_NAMES or ".cache" in path.parts:
                continue
            text = _read_searchable_text(path)
            if text is None:
                continue
            scanned += 1
            for name, pattern in IDENTITY_PATTERNS.items():
                match = pattern.search(text)
                if match:
                    line = text.count("\n", 0, match.start()) + 1
                    classification = _finding_classification(path)
                    findings.append(
                        {
                            "pattern": name,
                            "path": _portable(path),
                            "line": line,
                            "classification": classification,
                            "blocking": classification == "release_surface",
                        }
                    )
    blocking = [row for row in findings if row["blocking"]]
    return {
        "status": "passed" if not blocking else "failed",
        "roots": [_portable(Path(root)) for root in roots],
        "files_scanned": scanned,
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking),
        "quarantined_nonrelease_count": len(findings) - len(blocking),
        "findings": findings,
    }


def render_anonymity_audit(report: dict[str, Any]) -> str:
    lines = [
        "# Anonymity audit",
        "",
        "Status: `%s`." % report["status"],
        "",
        "Files scanned: `%s`; blocking findings: `%s`; quarantined non-release occurrences: `%s`."
        % (
            report["files_scanned"],
            report["blocking_finding_count"],
            report["quarantined_nonrelease_count"],
        ),
        "",
        "Scanned roots:",
        "",
    ]
    lines.extend("- `%s`" % root for root in report["roots"])
    if report["findings"]:
        lines.extend(["", "| Pattern | Path | Line | Classification |", "| --- | --- | ---: | --- |"])
        for row in report["findings"]:
            lines.append(
                "| %s | `%s` | %s | %s |"
                % (row["pattern"], row["path"], row["line"], row["classification"])
            )
    lines.extend(
        [
            "",
            "Non-release occurrences are third-party dataset text or legacy generated outputs excluded from the anonymous artifact.",
            "A release-surface finding blocks anonymous artifact or submission release.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_searchable_text(path: Path) -> str | None:
    if path.suffix.lower() == ".pdf":
        try:
            return subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def _heading_page(pages: list[str], heading: str) -> int | None:
    pattern = re.compile(r"\b(?:\d+\s+)?" + re.escape(heading) + r"\b")
    for index, page in enumerate(pages, start=1):
        if pattern.search(page):
            return index
    return None


def _finding_classification(path: Path) -> str:
    portable = _portable(path)
    normalized_parts = tuple(part.lower() for part in path.parts)
    if portable == "paper" or portable.startswith("paper/") or "paper" in normalized_parts:
        return "release_surface"
    if (
        portable == "artifacts/arr_anonymous"
        or portable.startswith("artifacts/arr_anonymous/")
        or any(
            normalized_parts[index : index + 2] == ("artifacts", "arr_anonymous")
            for index in range(max(0, len(normalized_parts) - 1))
        )
    ):
        return "release_surface"
    release_output_prefixes = (
        "benchmarks/contexttrace_bench/out/arr_full/",
        "benchmarks/contexttrace_bench/out/arr_full_after_review/",
        "benchmarks/contexttrace_bench/out/corrections/",
        "benchmarks/contexttrace_bench/out/rq4/simulated/",
        "benchmarks/contexttrace_bench/out/simulated_review/",
    )
    if portable.startswith(release_output_prefixes):
        return "release_surface"
    return "third_party_or_nonrelease_output"


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ARR page limits and anonymity.")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    parser.add_argument(
        "--roots",
        nargs="+",
        default=[
            str(PAPER_DIR),
            str(REPO_ROOT / "artifacts" / "arr_anonymous"),
            str(REPO_ROOT / "benchmarks" / "contexttrace_bench" / "out"),
        ],
    )
    parser.add_argument("--page-report", default=str(DEFAULT_PAGE_REPORT))
    parser.add_argument("--anonymity-report", default=str(DEFAULT_ANONYMITY_REPORT))
    args = parser.parse_args()
    page_report = audit_page_limit(args.pdf)
    anonymity_report = audit_anonymity(args.roots)
    Path(args.page_report).write_text(render_page_audit(page_report), encoding="utf-8")
    Path(args.anonymity_report).write_text(render_anonymity_audit(anonymity_report), encoding="utf-8")
    print("Page limit: %s/%s, fits=%s" % (page_report["content_pages_conservative"], page_report["arr_long_content_limit"], page_report["fits_arr_long_limit"]))
    print("Anonymity: %s, findings=%s" % (anonymity_report["status"], anonymity_report["finding_count"]))
    return 0 if page_report["fits_arr_long_limit"] and anonymity_report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
