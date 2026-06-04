from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from contexttrace.capture_endpoint import capture_endpoint_trace, capture_response_trace
from contexttrace.cli import main


class CaptureRagHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        response = {
            "answer": "Refunds are available within 30 days.",
            "contexts": [
                {
                    "id": "refund_policy",
                    "text": "Refunds are available within 30 days.",
                    "metadata": {"source": "refund_policy.md"},
                }
            ],
            "citations": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_id": "refund_policy",
                }
            ],
            "metadata": {"received": payload, "model": "local-rag"},
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return None


def test_capture_endpoint_trace_maps_nested_response_without_fabricating_citations():
    calls = []

    def caller(endpoint, method, headers, body, timeout):
        calls.append((endpoint, method, headers, body, timeout))
        return {
            "data": {
                "answer": "Refunds are available within 30 days.",
                "ctx": ["Refunds are available within 30 days."],
            },
            "metadata": {"model": "test-rag"},
        }

    captured = capture_endpoint_trace(
        endpoint="http://example.invalid/query",
        query="What is the refund policy?",
        headers={"X-Test": "1"},
        answer_path="$.data.answer",
        contexts_path="$.data.ctx",
        caller=caller,
    )

    assert calls[0][3] == {"question": "What is the refund policy?"}
    assert captured.trace.answer == "Refunds are available within 30 days."
    assert captured.trace.contexts[0].id == "chunk_1"
    assert captured.trace.contexts[0].text == "Refunds are available within 30 days."
    assert captured.trace.citations == []
    assert captured.trace.metadata["capture_source"] == "endpoint"
    assert captured.trace.metadata["model"] == "test-rag"


def test_capture_endpoint_cli_writes_trace_and_verification_report(tmp_path, capsys):
    server = HTTPServer(("127.0.0.1", 0), CaptureRagHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = "http://127.0.0.1:%s/query" % server.server_port
    trace_path = tmp_path / "captured_trace.json"
    report_path = tmp_path / "captured_report.html"

    try:
        exit_code = main(
            [
                "capture",
                "endpoint",
                "--endpoint",
                endpoint,
                "--query",
                "What is the refund policy?",
                "--out",
                str(trace_path),
                "--verify",
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
    assert "Trace: %s" % trace_path in output
    assert "Claims verified: 1" in output
    assert "Report: %s" % report_path in output

    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert payload["query"] == "What is the refund policy?"
    assert payload["contexts"][0]["id"] == "refund_policy"
    assert payload["citations"][0]["source_id"] == "refund_policy"
    assert payload["metadata"]["model"] == "local-rag"

    html = report_path.read_text(encoding="utf-8")
    assert "Reliability Summary" in html
    assert "Refunds are available within 30 days." in html


def test_capture_response_trace_maps_saved_response():
    captured = capture_response_trace(
        response={
            "result": {
                "answer": "Refunds are available within 30 days.",
                "documents": [
                    {
                        "id": "refund_policy",
                        "text": "Refunds are available within 30 days.",
                    }
                ],
            }
        },
        query="What is the refund policy?",
        response_source="saved.json",
        answer_path="$.result.answer",
        contexts_path="$.result.documents",
    )

    assert captured.trace.answer == "Refunds are available within 30 days."
    assert captured.trace.contexts[0].id == "refund_policy"
    assert captured.trace.metadata["capture_source"] == "saved_response"
    assert captured.trace.metadata["response_source"] == "saved.json"


def test_capture_response_cli_writes_trace_and_verification_report(tmp_path, capsys):
    response_path = tmp_path / "response.json"
    response_path.write_text(
        json.dumps(
            {
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {
                        "id": "refund_policy",
                        "text": "Refunds are available within 30 days.",
                    }
                ],
                "metadata": {"model": "local-rag"},
            }
        ),
        encoding="utf-8",
    )
    trace_path = tmp_path / "captured_response_trace.json"
    report_path = tmp_path / "captured_response_report.html"

    exit_code = main(
        [
            "capture",
            "response",
            str(response_path),
            "--query",
            "What is the refund policy?",
            "--out",
            str(trace_path),
            "--verify",
            "--report",
            "--report-out",
            str(report_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Trace: %s" % trace_path in output
    assert "Claims verified: 1" in output
    assert "Report: %s" % report_path in output

    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["capture_source"] == "saved_response"
    assert payload["metadata"]["model"] == "local-rag"
    assert report_path.exists()
