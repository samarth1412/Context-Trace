"""Minimal LlamaIndex RAG tracing example.

Install optional dependencies first:

    pip install contexttrace[llamaindex] llama-index

This example focuses on ContextTrace callback wiring. Replace the document
loading and index construction with your real LlamaIndex pipeline.
"""

from contexttrace import ContextTraceLlamaIndexCallbackHandler


def main() -> None:
    from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager

    handler = ContextTraceLlamaIndexCallbackHandler(
        api_key="ctx_test",
        project="support-rag",
        base_url="http://localhost:8000",
        trace_metadata={
            "environment": "local",
            "pipeline": "llamaindex-rag",
        },
    )
    Settings.callback_manager = CallbackManager([handler])

    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine()
    response = query_engine.query("What is the refund policy?")
    print(response)


if __name__ == "__main__":
    main()
