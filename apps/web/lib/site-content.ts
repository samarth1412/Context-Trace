export const quickstartSnippet = `from contexttrace import ContextTrace

ct = ContextTrace(mode="local", project="support-rag")
with ct.trace(query="What is the refund policy?") as trace:
    chunks = retriever.search(trace.query)
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    answer = llm.generate(trace.query, chunks[:5])
    trace.log_answer(answer, usage={"total_tokens": 1200})
    trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_12"}])
    result = trace.evaluate()`;

export const docsNav = [
  { href: "/docs", label: "Overview" },
  { href: "/docs/quickstart", label: "Quickstart" },
  { href: "/docs/sdk", label: "Python SDK" },
  { href: "/docs/reliability-score", label: "Reliability Score" },
  { href: "/docs/langchain", label: "LangChain" },
  { href: "/docs/llamaindex", label: "LlamaIndex" },
  { href: "/docs/api", label: "API Reference" }
];

export const docsPages = {
  quickstart: {
    title: "Quickstart",
    description: "Install the SDK, trace one RAG request, and export a reliability report.",
    sections: [
      {
        title: "Install",
        body: "Use local mode when you want file-backed traces and HTML reports without running the backend.",
        code: "pip install contexttrace\ncontexttrace init"
      },
      {
        title: "Trace a RAG request",
        body: "Keep your retriever and generator. ContextTrace records the query, evidence, answer, citations, and evaluation result.",
        code: quickstartSnippet
      },
      {
        title: "Open a report",
        body: "Reports can be created from local traces or fetched hosted traces.",
        code: "contexttrace trace list\ncontexttrace report --last --output report.html"
      }
    ]
  },
  sdk: {
    title: "Python SDK",
    description: "The SDK is a small trace logger with hosted, local, sync, and async clients.",
    sections: [
      {
        title: "Client configuration",
        body: "Configuration resolves from constructor arguments, environment variables, contexttrace.yaml, and SDK defaults.",
        code: `from contexttrace import ContextTrace

ct = ContextTrace(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
)`
      },
      {
        title: "Local mode",
        body: "Local mode stores trace JSON under .contexttrace and can generate HTML reports without a backend.",
        code: `ct = ContextTrace(mode="local", project="support-rag")
with ct.trace(query="What is the refund policy?") as trace:
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    trace.log_answer(answer)
    trace.export_report("report.html")`
      },
      {
        title: "Async client",
        body: "AsyncContextTrace mirrors the sync API for async RAG services.",
        code: `from contexttrace import AsyncContextTrace

ct = AsyncContextTrace(mode="local", project="support-rag")
async with ct.trace(query="What is the refund policy?") as trace:
    await trace.log_retrieval(chunks)
    await trace.log_answer(answer)
    result = await trace.evaluate()`
      }
    ]
  },
  "reliability-score": {
    title: "Reliability Score",
    description: "A practical diagnostic score for triaging RAG traces and eval summaries.",
    sections: [
      {
        title: "Purpose",
        body: "The score is an explainable diagnostic signal. It summarizes available metrics but does not replace citation support, unsupported claim rate, failure type, or raw trace evidence."
      },
      {
        title: "Components",
        body: "ContextTrace combines citation support, unsupported claim rate, failure rate, and optional retrieval quality, abstention quality, and token efficiency when those metrics are logged.",
        code: `{
  "score": 78,
  "grade": "B",
  "strengths": ["Citations are usually supported by evidence."],
  "weaknesses": ["Unsupported claims are present."],
  "recommendations": ["Review low-support citations."]
}`
      },
      {
        title: "Interpretation",
        body: "Use the grade for triage, then inspect the underlying metrics and failure report before making product or release decisions."
      }
    ]
  },
  langchain: {
    title: "LangChain Integration",
    description: "Capture inputs, retrieved documents, final output, metadata, token usage, and latency from LangChain callbacks.",
    sections: [
      {
        title: "Callback handler",
        body: "Attach the handler to your existing chain. Documents are converted into ContextTrace chunks from page_content and metadata.",
        code: `from contexttrace import ContextTraceCallbackHandler

handler = ContextTraceCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
)

result = chain.invoke(
    {"query": "What is the refund policy?"},
    config={"callbacks": [handler]},
)`
      },
      {
        title: "Captured fields",
        body: "ContextTrace records query/input, retrieved documents, selected context, final answer, metadata, latency, and token usage when available."
      }
    ]
  },
  llamaindex: {
    title: "LlamaIndex Integration",
    description: "Trace LlamaIndex query engines through a callback adapter that captures query, retrieved nodes, response, and source nodes.",
    sections: [
      {
        title: "Callback adapter",
        body: "Register the handler with LlamaIndex Settings or your callback manager.",
        code: `from contexttrace import ContextTraceLlamaIndexCallbackHandler
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

handler = ContextTraceLlamaIndexCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
)

Settings.callback_manager = CallbackManager([handler])
response = query_engine.query("What is the refund policy?")`
      },
      {
        title: "Node conversion",
        body: "Source nodes become chunks with chunk_id, content, source metadata, and relevance score."
      }
    ]
  },
  api: {
    title: "API Reference",
    description: "FastAPI endpoints for traces, citations, eval sets, external RAG APIs, playground runs, and agent events.",
    sections: [
      {
        title: "Trace lifecycle",
        body: "These endpoints match the SDK trace lifecycle.",
        code: `POST /v1/traces/start
POST /v1/traces/{trace_id}/retrieval
POST /v1/traces/{trace_id}/context
POST /v1/traces/{trace_id}/answer
POST /v1/traces/{trace_id}/citations
POST /v1/traces/{trace_id}/evaluate
GET  /v1/traces/{trace_id}`
      },
      {
        title: "Evaluation and integrations",
        body: "Eval sets, external endpoint testing, playground comparison, and agent events use the same bearer API key.",
        code: `POST /v1/eval-sets
POST /v1/external-endpoints/{id}/run-eval
POST /v1/playground/query
POST /v1/playground/compare
POST /v1/traces/{trace_id}/agent-events`
      }
    ]
  }
} as const;

export const useCases = [
  "RAG QA",
  "Support bots",
  "Legal/policy assistants",
  "AI agents",
  "Internal knowledge assistants",
  "LLM app evaluations"
];
