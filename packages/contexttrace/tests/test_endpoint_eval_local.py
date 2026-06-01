from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from contexttrace import ContextTrace
from contexttrace.endpoint_eval import run_endpoint_eval


class RagHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        response = {
            "answer": "Refunds are available within 30 days.",
            "contexts": [
                {
                    "id": "chunk_1",
                    "text": "Refunds are available within 30 days.",
                    "source": "refund_policy.md",
                }
            ],
            "citations": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_1",
                }
            ],
            "metadata": {"received": payload},
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return None


def test_endpoint_eval_creates_local_traces_and_report(tmp_path):
    dataset = tmp_path / "questions.json"
    dataset.write_text('[{"id":"q1","query":"What is the refund policy?"}]', encoding="utf-8")
    server = HTTPServer(("127.0.0.1", 0), RagHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = "http://127.0.0.1:%s/query" % server.server_port
    ct = ContextTrace(project="endpoint-rag", storage_path=str(tmp_path / "contexttrace.db"))

    try:
        result = run_endpoint_eval(
            dataset_path=str(dataset),
            endpoint=endpoint,
            contexttrace=ct,
            report_path=str(tmp_path / "eval_report.html"),
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result.questions_tested == 1
    assert result.failure_rate == 0.0
    assert result.avg_citation_support > 0.8
    assert result.report_path == str(tmp_path / "eval_report.html")
    assert (tmp_path / "eval_report.html").exists()
    assert len(ct.list_traces()) == 1


def test_endpoint_eval_jsonpath_mapping_with_fake_caller(tmp_path):
    dataset = tmp_path / "questions.json"
    dataset.write_text('["What is the refund policy?"]', encoding="utf-8")
    ct = ContextTrace(project="endpoint-rag", storage_path=str(tmp_path / "contexttrace.db"))

    def caller(endpoint, method, headers, body, timeout):
        return {
            "data": {
                "answer": "Refunds are available within 30 days.",
                "ctx": [{"id": "chunk_1", "text": "Refunds are available within 30 days."}],
                "sources": [{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}],
            }
        }

    result = run_endpoint_eval(
        dataset_path=str(dataset),
        endpoint="http://example.invalid/query",
        contexttrace=ct,
        answer_path="$.data.answer",
        contexts_path="$.data.ctx",
        citations_path="$.data.sources",
        caller=caller,
        generate_report=False,
    )

    assert result.questions_tested == 1
    assert ct.last_trace()["answer"]["answer"] == "Refunds are available within 30 days."
