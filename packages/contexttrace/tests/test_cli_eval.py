from contexttrace import ContextTrace
from contexttrace.cli import main
from contexttrace.evaluator import EvalThresholds, run_evaluation


class EvalTransport:
    def __init__(self, evaluations):
        self.calls = []
        self.evaluations = list(evaluations)
        self.trace_count = 0

    def post(self, path, payload=None):
        payload = payload or {}
        self.calls.append(("POST", path, payload))
        if path == "/v1/traces/start":
            self.trace_count += 1
            return {"trace_id": "trace_%s" % self.trace_count, "project_id": "project_1"}
        if path.endswith("/evaluate"):
            return self.evaluations.pop(0)
        return {"trace_id": "trace_%s" % self.trace_count, "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {}


def test_cli_eval_runner_sends_traces_and_writes_summary(tmp_path):
    dataset = tmp_path / "questions.json"
    dataset.write_text(
        """
        {
          "questions": [
            {
              "id": "refund_window",
              "question": "What is the refund policy?",
              "expected_answer": "Refunds are available within 30 days."
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.md"
    endpoint_calls = []
    transport = EvalTransport(
        [
            {
                "citation_checks": [
                    {
                        "claim": "Refunds are available within 30 days.",
                        "source_chunk_id": "chunk_1",
                        "verdict": "directly_supported",
                        "support_score": 0.95,
                        "reason": "Supported.",
                    }
                ],
                "failure": {"failure_type": "no_failure_detected"},
            }
        ]
    )

    def endpoint_caller(endpoint, question, timeout, headers):
        endpoint_calls.append((endpoint, question.question, headers))
        return {
            "answer": "Refunds are available within 30 days.",
            "retrieved_chunks": [
                {
                    "chunk_id": "chunk_1",
                    "content": "Refunds are available within 30 days.",
                    "source": "policy.md",
                    "score": 0.9,
                }
            ],
            "citations": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_1",
                }
            ],
            "usage": {"total_tokens": 120},
            "model": "test-rag",
        }

    summary = run_evaluation(
        dataset_path=str(dataset),
        endpoint="https://rag.example/query",
        api_key="ctx_test",
        project="ci-rag-eval",
        base_url="http://contexttrace.test",
        thresholds=EvalThresholds(
            min_citation_support=0.8,
            max_unsupported_claim_rate=0.2,
            max_failure_rate=0.1,
        ),
        summary_path=str(summary_path),
        endpoint_headers={"X-Test": "1"},
        endpoint_caller=endpoint_caller,
        contexttrace=ContextTrace(
            api_key="ctx_test",
            project="ci-rag-eval",
            transport=transport,
        ),
    )

    assert summary.failed is False
    assert summary.avg_citation_support == 0.95
    assert summary.unsupported_claim_rate == 0.0
    assert summary.failure_rate == 0.0
    assert summary_path.exists()
    assert "ContextTrace RAG Evaluation" in summary_path.read_text(encoding="utf-8")
    assert endpoint_calls == [("https://rag.example/query", "What is the refund policy?", {"X-Test": "1"})]
    assert transport.calls[0][1] == "/v1/traces/start"
    assert transport.calls[-1][1] == "/v1/traces/trace_1/evaluate"


def test_cli_eval_runner_fails_when_thresholds_are_violated(tmp_path):
    dataset = tmp_path / "questions.json"
    dataset.write_text('["What is the refund policy?"]', encoding="utf-8")
    transport = EvalTransport(
        [
            {
                "citation_checks": [
                    {
                        "claim": "Refunds are processed in two days.",
                        "source_chunk_id": "chunk_1",
                        "verdict": "unsupported",
                        "support_score": 0.1,
                        "reason": "Unsupported.",
                    }
                ],
                "failure": {"failure_type": "unsupported_answer"},
            }
        ]
    )

    def endpoint_caller(endpoint, question, timeout, headers):
        return {
            "answer": "Refunds are processed in two days.",
            "chunks": [{"id": "chunk_1", "text": "Refund processing varies."}],
            "citations": [
                {
                    "claim": "Refunds are processed in two days.",
                    "source_chunk_id": "chunk_1",
                }
            ],
        }

    summary = run_evaluation(
        dataset_path=str(dataset),
        endpoint="https://rag.example/query",
        api_key="ctx_test",
        project="ci-rag-eval",
        base_url="http://contexttrace.test",
        thresholds=EvalThresholds(
            min_citation_support=0.8,
            max_unsupported_claim_rate=0.2,
            max_failure_rate=0.0,
        ),
        summary_path=str(tmp_path / "summary.md"),
        endpoint_caller=endpoint_caller,
        contexttrace=ContextTrace(
            api_key="ctx_test",
            project="ci-rag-eval",
            transport=transport,
        ),
    )

    assert summary.failed is True
    assert summary.avg_citation_support == 0.1
    assert summary.unsupported_claim_rate == 1.0
    assert summary.failure_rate == 1.0


def test_cli_eval_command_invokes_runner(monkeypatch, tmp_path):
    dataset = tmp_path / "questions.json"
    dataset.write_text('["What is the refund policy?"]', encoding="utf-8")
    calls = []

    class Summary:
        failed = False
        markdown = "# Summary\n"

    def fake_run_evaluation(**kwargs):
        calls.append(kwargs)
        return Summary()

    monkeypatch.setattr("contexttrace.cli.run_evaluation", fake_run_evaluation)

    exit_code = main(
        [
            "eval",
            "--dataset",
            str(dataset),
            "--endpoint",
            "https://rag.example/query",
            "--api-key",
            "ctx_test",
            "--endpoint-header",
            "X-Test: 1",
        ]
    )

    assert exit_code == 0
    assert calls[0]["dataset_path"] == str(dataset)
    assert calls[0]["endpoint_headers"] == {"X-Test": "1"}
