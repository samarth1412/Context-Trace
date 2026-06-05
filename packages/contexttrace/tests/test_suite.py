from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from contexttrace.cli import main
from contexttrace.verify.suite import (
    add_trace_files_to_suite,
    create_suite_from_trace_files,
    list_suite_cases,
    prune_suite_cases,
    remove_suite_cases,
    run_suite,
    suite_failures,
)
from contexttrace.verify.suite_report import SuiteReportGenerator


def _write_trace(path, *, supported_context: bool = False):
    path.write_text(
        json.dumps(
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": (
                            "Refunds are processed within 5 business days."
                            if supported_context
                            else "Customers may request refunds within 30 days of purchase."
                        ),
                    }
                ],
                "metadata": {"run_id": "refund_processing"},
            }
        ),
        encoding="utf-8",
    )


class FixedRagHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        query = payload.get("question") or payload.get("query")
        response = {
            "answer": "Refunds are processed within 5 business days.",
            "contexts": [
                {
                    "id": "policy",
                    "text": "Refunds are processed within 5 business days.",
                }
            ],
            "metadata": {"query": query},
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return None


class BrokenRagHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        response = {
            "answer": "Refunds are processed within 5 business days.",
            "contexts": [
                {
                    "id": "policy",
                    "text": "Customers may request refunds within 30 days of purchase.",
                }
            ],
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return None


def _server(handler):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, "http://127.0.0.1:%s/query" % server.server_port


def test_create_suite_from_trace_files_stores_baseline_qa(tmp_path):
    trace_path = tmp_path / "bad_trace.json"
    _write_trace(trace_path)

    suite = create_suite_from_trace_files([str(trace_path)], name="refund-suite")

    assert suite["name"] == "refund-suite"
    assert suite["cases"][0]["id"] == "refund_processing"
    assert suite["cases"][0]["expected"]["policy"] == "must_pass"
    assert suite["cases"][0]["expected"]["max_risk_level"] == "low"
    assert suite["cases"][0]["baseline_qa"]["summary"]["risk_level"] in {"medium", "high"}


def test_run_suite_passes_when_saved_failure_is_fixed(tmp_path):
    trace_path = tmp_path / "bad_trace.json"
    _write_trace(trace_path)
    suite = create_suite_from_trace_files([str(trace_path)])
    server, thread, endpoint = _server(FixedRagHandler)

    try:
        result = run_suite(suite, endpoint=endpoint)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result["summary"]["status"] == "passed"
    assert result["summary"]["passed"] == 1
    assert result["summary"]["resolved_failures"] >= 1
    assert result["cases"][0]["comparison"]["summary"]["improved"] is True
    assert suite_failures(result, ("failed_case",)) == []


def test_run_suite_fails_when_failure_still_reproduces(tmp_path):
    trace_path = tmp_path / "bad_trace.json"
    _write_trace(trace_path)
    suite = create_suite_from_trace_files([str(trace_path)])
    server, thread, endpoint = _server(BrokenRagHandler)

    try:
        result = run_suite(suite, endpoint=endpoint)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result["summary"]["status"] == "failed"
    assert result["summary"]["failed"] == 1
    assert "risk level" in result["cases"][0]["failures"][0]
    assert "suite case failed" in suite_failures(result, ("failed_case",))


def test_suite_report_generation(tmp_path):
    trace_path = tmp_path / "bad_trace.json"
    report_path = tmp_path / "suite.html"
    _write_trace(trace_path)
    suite = create_suite_from_trace_files([str(trace_path)])
    server, thread, endpoint = _server(FixedRagHandler)

    try:
        result = run_suite(suite, endpoint=endpoint)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    written = SuiteReportGenerator().generate(result, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Regression Suite Report" in html
    assert "Suite Summary" in html
    assert "Resolved Failures" in html


def test_suite_add_list_remove_and_prune_operations(tmp_path):
    first_trace = tmp_path / "first.json"
    second_trace = tmp_path / "second.json"
    _write_trace(first_trace)
    _write_trace(second_trace, supported_context=True)
    first_payload = json.loads(first_trace.read_text(encoding="utf-8"))
    first_payload["metadata"]["run_id"] = "first_case"
    first_trace.write_text(json.dumps(first_payload), encoding="utf-8")
    second_payload = json.loads(second_trace.read_text(encoding="utf-8"))
    second_payload["metadata"]["run_id"] = "second_case"
    second_trace.write_text(json.dumps(second_payload), encoding="utf-8")

    suite = create_suite_from_trace_files([str(first_trace)], name="refund-suite")
    added = add_trace_files_to_suite(suite, [str(second_trace)])

    assert added["added_case_ids"] == ["second_case"]
    assert len(added["suite"]["cases"]) == 2
    rows = list_suite_cases(added["suite"])
    assert [row["id"] for row in rows] == ["first_case", "second_case"]

    removed = remove_suite_cases(added["suite"], ["second_case"])
    assert removed["removed_case_ids"] == ["second_case"]
    assert len(removed["suite"]["cases"]) == 1

    readded = add_trace_files_to_suite(removed["suite"], [str(second_trace)])
    result = {
        "summary": {"status": "failed"},
        "cases": [
            {"id": "first_case", "status": "failed"},
            {"id": "second_case", "status": "passed"},
        ],
    }
    pruned = prune_suite_cases(readded["suite"], result, statuses=("passed",))

    assert pruned["removed_case_ids"] == ["second_case"]
    assert [case["id"] for case in pruned["suite"]["cases"]] == ["first_case"]


def test_suite_add_replace_reuses_case_id(tmp_path):
    trace_path = tmp_path / "trace.json"
    _write_trace(trace_path)
    suite = create_suite_from_trace_files([str(trace_path)])

    added_without_replace = add_trace_files_to_suite(suite, [str(trace_path)])
    assert added_without_replace["added_case_ids"] == ["refund_processing_2"]
    assert len(added_without_replace["suite"]["cases"]) == 2

    added_with_replace = add_trace_files_to_suite(suite, [str(trace_path)], replace=True)
    assert added_with_replace["added_case_ids"] == ["refund_processing"]
    assert added_with_replace["replaced"] == 1
    assert len(added_with_replace["suite"]["cases"]) == 1


def test_suite_cli_create_run_and_report(tmp_path, capsys):
    trace_path = tmp_path / "bad_trace.json"
    suite_path = tmp_path / "suite.json"
    results_path = tmp_path / "suite-results.json"
    report_path = tmp_path / "suite.html"
    _write_trace(trace_path)
    server, thread, endpoint = _server(FixedRagHandler)

    try:
        assert main(["suite", "create", str(trace_path), "--out", str(suite_path)]) == 0
        capsys.readouterr()
        exit_code = main(
            [
                "suite",
                "run",
                str(suite_path),
                "--endpoint",
                endpoint,
                "--out",
                str(results_path),
                "--report",
                "--report-out",
                str(report_path),
            ]
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Status: passed" in output
    assert results_path.exists()
    assert report_path.exists()

    second_report = tmp_path / "suite-again.html"
    assert main(["suite", "report", str(results_path), "--out", str(second_report)]) == 0
    assert second_report.exists()


def test_suite_cli_add_list_remove_and_prune(tmp_path, capsys):
    first_trace = tmp_path / "first.json"
    second_trace = tmp_path / "second.json"
    suite_path = tmp_path / "suite.json"
    results_path = tmp_path / "results.json"
    _write_trace(first_trace)
    _write_trace(second_trace, supported_context=True)
    first_payload = json.loads(first_trace.read_text(encoding="utf-8"))
    first_payload["metadata"]["run_id"] = "first_case"
    first_trace.write_text(json.dumps(first_payload), encoding="utf-8")
    second_payload = json.loads(second_trace.read_text(encoding="utf-8"))
    second_payload["metadata"]["run_id"] = "second_case"
    second_trace.write_text(json.dumps(second_payload), encoding="utf-8")

    assert main(["suite", "create", str(first_trace), "--out", str(suite_path)]) == 0
    capsys.readouterr()
    assert main(["suite", "add", str(suite_path), str(second_trace)]) == 0
    add_output = capsys.readouterr().out
    assert "Added: 1" in add_output
    assert "second_case" in add_output

    assert main(["suite", "list", str(suite_path)]) == 0
    list_output = capsys.readouterr().out
    assert "first_case" in list_output
    assert "second_case" in list_output

    results_path.write_text(
        json.dumps(
            {
                "summary": {"status": "failed"},
                "cases": [
                    {"id": "first_case", "status": "failed"},
                    {"id": "second_case", "status": "passed"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["suite", "prune", str(suite_path), "--results", str(results_path)]) == 0
    prune_output = capsys.readouterr().out
    assert "Removed: 1" in prune_output
    assert "second_case" in prune_output

    assert main(["suite", "add", str(suite_path), str(second_trace)]) == 0
    capsys.readouterr()
    assert main(["suite", "remove", str(suite_path), "second_case"]) == 0
    remove_output = capsys.readouterr().out
    assert "Removed: 1" in remove_output
