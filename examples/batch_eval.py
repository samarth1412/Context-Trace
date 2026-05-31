"""Create an eval set from existing traces and aggregate reliability metrics."""

from contexttrace import ContextTrace


def main() -> None:
    ct = ContextTrace(
        api_key="ctx_test",
        project="support-rag",
        base_url="http://localhost:8000",
    )

    eval_set = ct.create_eval_set(
        "refund-policy-regression",
        metadata={"example": "batch_eval"},
    )
    eval_set_id = eval_set["eval_set_id"]

    ct.add_eval_questions(
        eval_set_id,
        [
            {
                "question": "What is the refund policy?",
                "trace_id": "replace-with-existing-trace-id",
                "expected_answer": "Refunds are available within 30 days.",
                "metadata": {"category": "refunds"},
            },
            {
                "question": "Can final-sale items be refunded?",
                "trace_id": "replace-with-existing-trace-id",
                "metadata": {"category": "refunds"},
            },
        ],
    )

    summary = ct.evaluate_existing_traces(eval_set_id)
    print(summary)


if __name__ == "__main__":
    main()
