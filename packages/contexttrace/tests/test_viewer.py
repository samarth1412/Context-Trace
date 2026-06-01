from contexttrace import ContextTrace
from contexttrace.viewer import create_viewer_app


def _request(app, path):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app({"PATH_INFO": path}, start_response)).decode("utf-8")
    return captured["status"], body


def test_local_viewer_returns_pages(tmp_path):
    storage_path = str(tmp_path / "contexttrace.db")
    ct = ContextTrace(project="viewer-rag", storage_path=storage_path)
    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval([{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}])
        trace.log_context(chunk_ids=["chunk_1"])
        trace.log_answer("Refunds are available within 30 days.")
        trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}])
        trace.evaluate()

    app = create_viewer_app(storage_path)
    status, home = _request(app, "/")
    assert status == "200 OK"
    assert "ContextTrace Local Viewer" in home

    status, traces = _request(app, "/traces")
    assert status == "200 OK"
    assert trace.trace_id in traces

    status, detail = _request(app, "/traces/%s" % trace.trace_id)
    assert status == "200 OK"
    assert "ContextTrace Report" in detail

    status, eval_runs = _request(app, "/eval-runs")
    assert status == "200 OK"
    assert "Eval Runs" in eval_runs

    status, reports = _request(app, "/reports")
    assert status == "200 OK"
    assert "Reports" in reports
