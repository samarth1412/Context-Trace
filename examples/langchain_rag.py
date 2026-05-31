"""Minimal LangChain RAG tracing example.

Install optional dependencies first:

    pip install contexttrace[langchain] langchain

This example focuses on the ContextTrace callback wiring. Replace the retriever
and chain objects with your real LangChain pipeline.
"""

from contexttrace import ContextTraceCallbackHandler


def build_chain():
    """Return your LangChain RAG chain."""
    raise NotImplementedError("Wire this to your LangChain RAG chain.")


def main() -> None:
    callback = ContextTraceCallbackHandler(
        api_key="ctx_test",
        project="support-rag",
        base_url="http://localhost:8000",
        trace_metadata={
            "environment": "local",
            "pipeline": "langchain-rag",
        },
    )

    chain = build_chain()
    result = chain.invoke(
        {"query": "What is the refund policy?"},
        config={"callbacks": [callback]},
    )
    print(result)


if __name__ == "__main__":
    main()
