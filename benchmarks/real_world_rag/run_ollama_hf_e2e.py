from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "packages" / "contexttrace"
SCRATCH_ROOT = ROOT / ".contexttrace" / "real_world_repos"
REPO_URL = "https://github.com/taha-parsayan/Ollama-and-HuggingFace-RAG-Engine"
REPO_PATH = SCRATCH_ROOT / "ollama-hf-rag-engine"
TRACE_PATH = ROOT / "benchmarks" / "real_world_rag" / "traces" / "ollama_hf_e2e_petmri.json"
VERIFY_REPORT_PATH = ROOT / "benchmarks" / "real_world_rag" / "reports" / "ollama_hf_e2e_petmri_verify.html"
AUDIT_REPORT_PATH = ROOT / "benchmarks" / "real_world_rag" / "reports" / "ollama_hf_e2e_petmri_audit.html"
RESULT_PATH = ROOT / "benchmarks" / "real_world_rag" / "ollama_hf_e2e_result.json"

EMBEDDING_MODEL = os.environ.get("CONTEXTTRACE_E2E_EMBEDDINGS", "nomic-embed-text")
GENERATION_MODEL = os.environ.get("CONTEXTTRACE_E2E_LLM", "phi3")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
QUESTION = os.environ.get(
    "CONTEXTTRACE_E2E_QUESTION",
    "What are the main advantages of PET/MRI compared with PET/CT?",
)


def main() -> int:
    _ensure_import_path()
    from contexttrace.capture import capture_rag_trace, write_rag_trace
    from contexttrace.verify import audit_trace_with_corpus, verify_trace
    from contexttrace.verify.audit_report import AuditReportGenerator
    from contexttrace.verify.report import VerifyReportGenerator
    from contexttrace.verify.schema import TraceContext

    repo_state = _ensure_repo()
    module = _load_repo_main()

    # The cloned project imports langchain_ollama, whose current client expects a newer
    # Ollama `/api/embed` endpoint. This runner keeps the app pipeline intact but uses
    # langchain_community's Ollama wrappers, which support this machine's Ollama 0.1.x.
    from langchain_community.chat_models import ChatOllama
    from langchain_community.embeddings import OllamaEmbeddings

    previous_cwd = Path.cwd()
    started = time.perf_counter()
    try:
        os.chdir(REPO_PATH)
        module.initialize_environment()
        texts = module.load_txts_from_directory("data")
        chunks = module.chunk_documents(texts, chunk_size=1000, chunk_overlap=100)

        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
        dimensions = len(embeddings.embed_query("test query"))
        vector_store = module.create_vector_store(embedding_function=embeddings, dimensions=dimensions)
        documents = [
            module.Document(
                page_content=chunk,
                metadata={
                    "source": "data/PETMRI.txt",
                    "chunk_index": index,
                    "repo": REPO_URL,
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        vector_store.add_documents(documents=documents)

        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 3, "fetch_k": 20, "lambda_mult": 0.5},
        )
        retrieved_docs = retriever.invoke(QUESTION)

        model = ChatOllama(
            model=GENERATION_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            num_predict=120,
        )
        prompt = module.ChatPromptTemplate.from_template(
            """
You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question.
If you do not know, say you do not know.
Answer in bullet points from the context only.
Question: {question}
Context: {context}
Answer:
""".strip()
        )
        chain = (
            {"context": retriever | module.format_docs, "question": module.RunnablePassthrough()}
            | prompt
            | model
            | module.StrOutputParser()
        )
        answer = chain.invoke(QUESTION)
    finally:
        os.chdir(previous_cwd)

    trace = capture_rag_trace(
        query=QUESTION,
        answer=answer,
        contexts=retrieved_docs,
        metadata={
            "validation": "real_world_rag_e2e",
            "repo": REPO_URL,
            "repo_state": repo_state,
            "retriever": "FAISS.as_retriever(search_type='mmr', k=3, fetch_k=20, lambda_mult=0.5)",
            "embedding_model": EMBEDDING_MODEL,
            "generation_model": GENERATION_MODEL,
            "ollama_base_url": OLLAMA_BASE_URL,
            "compatibility_note": "Used langchain_community Ollama wrappers because installed Ollama exposes /api/embeddings, while current langchain_ollama expects /api/embed.",
        },
        context_id_prefix="ollama_hf_doc",
    )
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_rag_trace(trace, TRACE_PATH)

    corpus_contexts = [
        TraceContext(
            id="ollama_hf_corpus_%s" % index,
            text=document.page_content,
            metadata=dict(document.metadata),
        )
        for index, document in enumerate(documents)
    ]
    verify_result = verify_trace(trace, mode="semantic")
    audit_result = audit_trace_with_corpus(
        trace,
        corpus_contexts,
        corpus_path=REPO_URL,
        mode="semantic",
    )
    VerifyReportGenerator().generate(verify_result, trace, path=str(VERIFY_REPORT_PATH))
    AuditReportGenerator().generate(audit_result, trace, path=str(AUDIT_REPORT_PATH))

    result = {
        "status": "completed",
        "repo": REPO_URL,
        "question": QUESTION,
        "answer": answer,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "retrieved_contexts": [
            {
                "id": context.id,
                "metadata": context.metadata,
                "preview": context.text[:240],
            }
            for context in trace.contexts
        ],
        "verify_summary": verify_result["summary"],
        "audit_summary": audit_result["summary"],
        "trace_path": _rel(TRACE_PATH),
        "verify_report_path": _rel(VERIFY_REPORT_PATH),
        "audit_report_path": _rel(AUDIT_REPORT_PATH),
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def _ensure_import_path() -> None:
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))


def _ensure_repo() -> str:
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    if (REPO_PATH / ".git").exists():
        return "already_cloned"
    if REPO_PATH.exists() and any(REPO_PATH.iterdir()):
        return "present_without_git"
    if REPO_PATH.exists():
        REPO_PATH.rmdir()
    subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, str(REPO_PATH)],
        cwd=str(ROOT),
        check=True,
    )
    return "cloned"


def _load_repo_main() -> Any:
    spec = importlib.util.spec_from_file_location("ollama_hf_rag_main", REPO_PATH / "main.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load %s." % (REPO_PATH / "main.py"))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(REPO_PATH))
    spec.loader.exec_module(module)
    return module


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
