import asyncio

from contexttrace import AsyncContextTrace


def test_async_contexttrace_local_trace_flow(tmp_path):
    async def scenario():
        ct = AsyncContextTrace(
            mode="local",
            project="support-rag",
            local_store_dir=str(tmp_path / "store"),
        )
        async with ct.trace(query="What is the refund policy?") as trace:
            await trace.log_retrieval(
                [{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}]
            )
            await trace.log_context(chunk_ids=["chunk_1"])
            await trace.log_answer("Refunds are available within 30 days.")
            await trace.log_citations(
                [
                    {
                        "claim": "Refunds are available within 30 days.",
                        "source_chunk_id": "chunk_1",
                    }
                ]
            )
            evaluation = await trace.evaluate()
            fetched = await trace.fetch()
        await ct.close()
        return evaluation, fetched

    evaluation, fetched = asyncio.run(scenario())

    assert evaluation["failure"]["failure_type"] == "no_failure_detected"
    assert fetched["status"] == "evaluated"
