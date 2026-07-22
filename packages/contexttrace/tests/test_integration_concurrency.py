import asyncio

from contexttrace import (
    ContextTrace,
    ContextTraceCallbackHandler,
    ContextTraceLangGraphTracer,
    ContextTraceLlamaIndexCallbackHandler,
)


class RunTransport:
    def __init__(self):
        self.calls = []
        self.count = 0

    def post(self, path, payload=None):
        payload = payload or {}
        if path == "/v1/traces/start":
            self.count += 1
            trace_id = "trace_%s" % self.count
            self.calls.append((path, payload, trace_id))
            return {"trace_id": trace_id, "project_id": "project"}
        self.calls.append((path, payload, None))
        return {"accepted": 1}

    def get(self, path):
        return {}


def _answer_routes(transport):
    return {
        payload["answer"]: path
        for path, payload, _ in transport.calls
        if path.endswith("/answer")
    }


def test_langchain_handler_separates_interleaved_run_ids():
    transport = RunTransport()
    handler = ContextTraceCallbackHandler(client=ContextTrace(transport=transport))

    async def run(run_id, query, answer):
        handler.on_chain_start({"name": "qa"}, {"query": query}, run_id=run_id)
        await asyncio.sleep(0)
        handler.on_chain_end({"answer": answer}, run_id=run_id)

    async def main():
        await asyncio.gather(run("a", "query a", "answer a"), run("b", "query b", "answer b"))

    asyncio.run(main())
    routes = _answer_routes(transport)
    assert routes["answer a"] != routes["answer b"]


def test_llamaindex_handler_separates_interleaved_event_ids():
    transport = RunTransport()
    handler = ContextTraceLlamaIndexCallbackHandler(client=ContextTrace(transport=transport))

    async def run(event_id, query, answer):
        handler.on_event_start("query", {"query_str": query}, event_id=event_id, parent_id="shared-root")
        await asyncio.sleep(0)
        handler.on_event_end("query", {"response": answer}, event_id=event_id)

    async def main():
        await asyncio.gather(run("a", "query a", "answer a"), run("b", "query b", "answer b"))

    asyncio.run(main())
    routes = _answer_routes(transport)
    assert routes["answer a"] != routes["answer b"]


def test_langgraph_tracer_separates_explicit_run_ids():
    transport = RunTransport()
    tracer = ContextTraceLangGraphTracer(client=ContextTrace(transport=transport))
    tracer.start_trace("query a", run_id="a")
    tracer.start_trace("query b", run_id="b")
    tracer.end_trace(answer="answer a", run_id="a")
    tracer.end_trace(answer="answer b", run_id="b")
    routes = _answer_routes(transport)
    assert routes["answer a"] != routes["answer b"]


def test_langchain_handler_isolates_many_adversarially_interleaved_runs():
    transport = RunTransport()
    handler = ContextTraceCallbackHandler(client=ContextTrace(transport=transport))
    run_count = 32

    async def run(index):
        run_id = "run-%02d" % index
        handler.on_chain_start({"name": "qa"}, {"query": "query %02d" % index}, run_id=run_id)
        await asyncio.sleep(0 if index % 2 else 0.001)
        handler.on_chain_end({"answer": "answer %02d" % index}, run_id=run_id)

    async def main():
        await asyncio.gather(*(run(index) for index in range(run_count)))

    asyncio.run(main())
    routes = _answer_routes(transport)
    assert len(routes) == run_count
    assert len(set(routes.values())) == run_count
