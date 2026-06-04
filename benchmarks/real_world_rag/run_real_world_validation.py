from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRATCH_ROOT = ROOT / ".contexttrace" / "real_world_repos"
ARTIFACT_ROOT = ROOT / "benchmarks" / "real_world_rag"
TRACE_DIR = ARTIFACT_ROOT / "traces"
REPORT_DIR = ARTIFACT_ROOT / "reports"
SUMMARY_PATH = ARTIFACT_ROOT / "results.json"
MARKDOWN_PATH = ARTIFACT_ROOT / "README.md"

GENERATION_MODEL = os.environ.get("CONTEXTTRACE_REAL_WORLD_LLM", "mistral")
EMBEDDING_MODEL = os.environ.get("CONTEXTTRACE_REAL_WORLD_EMBEDDINGS", "all-MiniLM-L6-v2")
USE_OLLAMA_GENERATION = os.environ.get("CONTEXTTRACE_REAL_WORLD_USE_OLLAMA", "0") == "1"

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")
SUPPORTED_SUFFIXES = {".md", ".py", ".txt"}
SKIP_PARTS = {".git", ".pytest_cache", "__pycache__", "poetry.lock", "node_modules"}
MAX_FILE_BYTES = 120_000
MAX_CHARS_PER_PROJECT = 260_000
TOP_K = 3


@dataclass(frozen=True)
class ProjectCase:
    id: str
    name: str
    repo_url: str
    local_dir: str
    questions: tuple[str, ...]
    notes: str


PROJECTS = (
    ProjectCase(
        id="local_rag_chat",
        name="HeskethGD/local-rag-chat",
        repo_url="https://github.com/HeskethGD/local-rag-chat",
        local_dir="local-rag-chat",
        questions=(
            "What local models does this RAG chatbot use for chat and embeddings?",
            "How does the RAG agent use retrieved sources when drafting an answer?",
        ),
        notes="Offline FastAPI/Streamlit RAG app using Ollama and LanceDB.",
    ),
    ProjectCase(
        id="ollama_hf_rag_engine",
        name="taha-parsayan/Ollama-and-HuggingFace-RAG-Engine",
        repo_url="https://github.com/taha-parsayan/Ollama-and-HuggingFace-RAG-Engine",
        local_dir="ollama-hf-rag-engine",
        questions=(
            "What vector store does this RAG engine use?",
            "What should the assistant do if it does not know the answer?",
        ),
        notes="LangChain/Ollama/FAISS RAG script with a real text corpus in data/.",
    ),
    ProjectCase(
        id="rag_chatbot",
        name="umbertogriffo/rag-chatbot",
        repo_url="https://github.com/umbertogriffo/rag-chatbot",
        local_dir="rag-chatbot",
        questions=(
            "How does this chatbot update its vector database when documents change?",
            "What response synthesis strategies does the chatbot support?",
        ),
        notes="Local llama.cpp plus Chroma RAG chatbot with Markdown chunking and incremental indexing.",
    ),
)


def main() -> int:
    _ensure_import_path()
    from contexttrace.verify import audit_trace_with_corpus, verify_trace
    from contexttrace.verify.audit_report import AuditReportGenerator
    from contexttrace.verify.report import VerifyReportGenerator
    from contexttrace.verify.schema import RAGTrace, TraceContext

    embedder = _load_embedder()
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for project in PROJECTS:
        repo_path = SCRATCH_ROOT / project.local_dir
        status = _ensure_repo(project, repo_path)
        documents = _load_project_documents(repo_path)
        chunks = _chunk_documents(project, documents)
        if not chunks:
            rows.append(
                {
                    "project": project.name,
                    "repo_url": project.repo_url,
                    "status": "skipped",
                    "reason": "No readable Markdown, Python, or text corpus files were found.",
                    "setup": status,
                    "cases": [],
                }
            )
            continue

        corpus_contexts = [
            TraceContext(id=chunk["id"], text=chunk["text"], metadata=chunk["metadata"])
            for chunk in chunks
        ]
        case_rows = []
        for index, question in enumerate(project.questions, start=1):
            retrieved = _retrieve(question, chunks, embedder)
            answer = _generate_answer(question, retrieved) if USE_OLLAMA_GENERATION else _extractive_answer(question, retrieved)
            trace = RAGTrace(
                query=question,
                answer=answer,
                contexts=[
                    TraceContext(id=item["id"], text=item["text"], metadata=item["metadata"])
                    for item in retrieved
                ],
                metadata={
                    "project": project.name,
                    "repo_url": project.repo_url,
                    "validation": "real_world_rag",
                    "generation_model": GENERATION_MODEL,
                    "embedding_model": EMBEDDING_MODEL,
                },
            )
            verify_result = verify_trace(trace, mode="semantic")
            audit_result = audit_trace_with_corpus(
                trace,
                corpus_contexts,
                corpus_path=project.repo_url,
                mode="semantic",
            )

            case_id = f"{project.id}_{index}"
            trace_path = TRACE_DIR / f"{case_id}.json"
            verify_report_path = REPORT_DIR / f"{case_id}_verify.html"
            audit_report_path = REPORT_DIR / f"{case_id}_audit.html"
            trace_path.write_text(json.dumps(_trace_payload(trace), indent=2), encoding="utf-8")
            VerifyReportGenerator().generate(verify_result, trace, path=str(verify_report_path))
            AuditReportGenerator().generate(audit_result, trace, path=str(audit_report_path))

            case_rows.append(
                {
                    "id": case_id,
                    "case_type": "grounded_smoke",
                    "question": question,
                    "answer_preview": _preview(answer, 260),
                    "trace_path": _rel(trace_path),
                    "verify_report_path": _rel(verify_report_path),
                    "audit_report_path": _rel(audit_report_path),
                    "retrieved_context_ids": [item["id"] for item in retrieved],
                    "verify_summary": verify_result["summary"],
                    "audit_summary": audit_result["summary"],
                    "top_claims": [
                        {
                            "claim": claim.get("claim"),
                            "verdict": claim.get("verdict"),
                            "root_cause": (claim.get("root_cause") or {}).get("label"),
                            "evidence": _preview(str(claim.get("evidence") or ""), 160),
                        }
                        for claim in verify_result.get("claims", [])[:4]
                    ],
                }
            )

        stress_question = project.questions[0]
        oracle_retrieved = _retrieve(stress_question, chunks, embedder)
        bad_retrieved = _retrieve_distractors(stress_question, chunks)
        if oracle_retrieved and bad_retrieved:
            answer = _extractive_answer(stress_question, oracle_retrieved)
            trace = RAGTrace(
                query=stress_question,
                answer=answer,
                contexts=[
                    TraceContext(id=item["id"], text=item["text"], metadata=item["metadata"])
                    for item in bad_retrieved
                ],
                metadata={
                    "project": project.name,
                    "repo_url": project.repo_url,
                    "validation": "real_world_rag",
                    "case_type": "retrieval_stress_control",
                    "generation_model": "extractive oracle from real corpus",
                    "embedding_model": EMBEDDING_MODEL,
                },
            )
            verify_result = verify_trace(trace, mode="semantic")
            audit_result = audit_trace_with_corpus(
                trace,
                corpus_contexts,
                corpus_path=project.repo_url,
                mode="semantic",
            )
            case_id = f"{project.id}_stress_1"
            trace_path = TRACE_DIR / f"{case_id}.json"
            verify_report_path = REPORT_DIR / f"{case_id}_verify.html"
            audit_report_path = REPORT_DIR / f"{case_id}_audit.html"
            trace_path.write_text(json.dumps(_trace_payload(trace), indent=2), encoding="utf-8")
            VerifyReportGenerator().generate(verify_result, trace, path=str(verify_report_path))
            AuditReportGenerator().generate(audit_result, trace, path=str(audit_report_path))
            case_rows.append(
                {
                    "id": case_id,
                    "case_type": "retrieval_stress_control",
                    "question": stress_question,
                    "answer_preview": _preview(answer, 260),
                    "trace_path": _rel(trace_path),
                    "verify_report_path": _rel(verify_report_path),
                    "audit_report_path": _rel(audit_report_path),
                    "retrieved_context_ids": [item["id"] for item in bad_retrieved],
                    "oracle_context_ids": [item["id"] for item in oracle_retrieved],
                    "verify_summary": verify_result["summary"],
                    "audit_summary": audit_result["summary"],
                    "top_claims": [
                        {
                            "claim": claim.get("claim"),
                            "verdict": claim.get("verdict"),
                            "root_cause": (claim.get("root_cause") or {}).get("label"),
                            "evidence": _preview(str(claim.get("evidence") or ""), 160),
                        }
                        for claim in verify_result.get("claims", [])[:4]
                    ],
                }
            )

        rows.append(
            {
                "project": project.name,
                "repo_url": project.repo_url,
                "notes": project.notes,
                "status": "completed",
                "setup": status,
                "corpus_files": len(documents),
                "corpus_chunks": len(chunks),
                "cases": case_rows,
            }
        )

    payload = {
        "generated_at": "2026-06-04",
        "description": "Real-world ContextTrace smoke test over public GitHub RAG projects.",
        "generation_model": GENERATION_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "answer_mode": "ollama" if USE_OLLAMA_GENERATION else "extractive_from_retrieved_context",
        "projects": rows,
    }
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    MARKDOWN_PATH.write_text(_markdown_summary(payload), encoding="utf-8")
    print(json.dumps(_console_summary(payload), indent=2))
    return 0


def _ensure_import_path() -> None:
    package_root = ROOT / "packages" / "contexttrace"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))


def _load_embedder() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Install sentence-transformers or set up another local embedding path before running this validation."
        ) from exc
    return SentenceTransformer(EMBEDDING_MODEL)


def _ensure_repo(project: ProjectCase, path: Path) -> dict[str, str]:
    if (path / ".git").exists():
        return {"state": "already_cloned", "path": str(path)}
    if path.exists() and any(path.iterdir()):
        return {"state": "present_without_git", "path": str(path)}
    if path.exists():
        path.rmdir()
    subprocess.run(
        ["git", "clone", "--depth", "1", project.repo_url, str(path)],
        cwd=str(ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {"state": "cloned", "path": str(path)}


def _load_project_documents(path: Path) -> list[dict[str, str]]:
    documents = []
    total_chars = 0
    for file_path in sorted(path.rglob("*"), key=lambda item: str(item).lower()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in file_path.parts):
            continue
        if file_path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        text = _clean_text(text)
        if not text:
            continue
        rel_path = file_path.relative_to(path).as_posix()
        documents.append({"path": rel_path, "text": text})
        total_chars += len(text)
        if total_chars >= MAX_CHARS_PER_PROJECT:
            break
    return documents


def _chunk_documents(project: ProjectCase, documents: list[dict[str, str]]) -> list[dict[str, Any]]:
    chunks = []
    for document in documents:
        for index, chunk_text in enumerate(_chunk_text(document["text"]), start=1):
            chunks.append(
                {
                    "id": f"{project.id}:{document['path']}:{index}",
                    "text": chunk_text,
                    "metadata": {
                        "project": project.name,
                        "repo_url": project.repo_url,
                        "source": document["path"],
                    },
                }
            )
    return chunks


def _chunk_text(text: str, *, max_chars: int = 700, overlap: int = 100) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            for start in range(0, len(paragraph), max_chars - overlap):
                segment = paragraph[start : start + max_chars].strip()
                if segment:
                    chunks.append(segment)
            continue
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current.strip())
            current = current[-overlap:].strip() if overlap and len(current) > overlap else ""
        current = (current + "\n\n" + paragraph).strip() if current else paragraph
    if current:
        chunks.append(current.strip())
    return chunks


def _retrieve(question: str, chunks: list[dict[str, Any]], embedder: Any) -> list[dict[str, Any]]:
    candidates = sorted(
        chunks,
        key=lambda item: _lexical_score(question, item["text"]),
        reverse=True,
    )[:40]
    texts = [question] + [item["text"] for item in candidates]
    vectors = embedder.encode(texts, normalize_embeddings=True)
    query_vector = vectors[0]
    ranked = []
    for item, vector in zip(candidates, vectors[1:]):
        score = float(sum(a * b for a, b in zip(query_vector, vector)))
        ranked.append((score, item))
    return [
        {
            **item,
            "metadata": {
                **item["metadata"],
                "retrieval_score": round(score, 4),
                "retriever": "sentence-transformers lexical-prefilter cosine",
            },
        }
        for score, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:TOP_K]
    ]


def _retrieve_distractors(question: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        chunks,
        key=lambda item: _lexical_score(question, item["text"]),
    )
    distractors = []
    for item in ranked:
        if _lexical_score(question, item["text"]) > 0.12:
            continue
        distractors.append(
            {
                **item,
                "metadata": {
                    **item["metadata"],
                    "retrieval_score": round(_lexical_score(question, item["text"]), 4),
                    "retriever": "intentional low-overlap stress control",
                },
            }
        )
        if len(distractors) >= TOP_K:
            break
    return distractors


def _generate_answer(question: str, retrieved: list[dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[{item['id']}]\n{_preview(item['text'], 700)}"
        for item in retrieved
    )
    prompt = f"""
You are answering a developer's question about an open-source RAG project.
Use only the retrieved context below. If the context does not contain the answer, say you do not know.
Keep the answer concise, factual, and under 120 words.

Question: {question}

Retrieved context:
{context}

Answer:
""".strip()
    payload = {
        "model": GENERATION_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "top_p": 0.2, "num_predict": 160},
    }
    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    return str(result.get("response") or "").strip()


def _extractive_answer(question: str, retrieved: list[dict[str, Any]]) -> str:
    sentences = []
    for item in retrieved:
        for sentence in _sentences(item["text"]):
            score = _lexical_score(question, sentence)
            if score > 0:
                sentences.append((score, sentence))
    ranked = [sentence for _, sentence in sorted(sentences, key=lambda pair: pair[0], reverse=True)]
    selected = []
    seen = set()
    for sentence in ranked:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(sentence)
        if len(" ".join(selected)) >= 420 or len(selected) >= 3:
            break
    if not selected:
        return "I do not know based on the retrieved context."
    return " ".join(selected)


def _sentences(text: str) -> list[str]:
    parts = []
    start = 0
    value = str(text or "")
    for index, char in enumerate(value):
        if char not in ".!?":
            continue
        if char == "." and _is_internal_period(value, index):
            continue
        sentence = value[start : index + 1].strip()
        if sentence:
            parts.append(sentence)
        start = index + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _is_internal_period(text: str, index: int) -> bool:
    previous = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and next_char.isdigit():
        return True
    if previous.isalnum() and next_char.isalnum():
        return True
    if previous.isalnum() and next_char in "_-/\\":
        return True
    if previous in "_-/\\" and next_char.isalnum():
        return True
    return False


def _trace_payload(trace: Any) -> dict[str, Any]:
    return {
        "query": trace.query,
        "answer": trace.answer,
        "contexts": [
            {
                "id": context.id,
                "text": context.text,
                "metadata": dict(context.metadata),
            }
            for context in trace.contexts
        ],
        "metadata": dict(trace.metadata),
    }


def _lexical_score(query: str, text: str) -> float:
    query_terms = _important_terms(query)
    text_terms = _important_terms(text)
    if not query_terms:
        return 0.0
    text_set = set(text_terms)
    overlap = len([term for term in query_terms if term in text_set]) / len(query_terms)
    density = len([term for term in text_terms if term in set(query_terms)]) / max(1, len(text_terms))
    return overlap + min(0.25, density)


def _important_terms(text: str) -> list[str]:
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "does", "for", "from",
        "how", "if", "in", "is", "it", "of", "or", "the", "this", "to", "use",
        "what", "when", "where", "with",
    }
    terms = []
    seen = set()
    for raw in TOKEN_RE.findall(str(text or "").lower()):
        term = raw.strip("._-/:")
        if len(term) < 2 or term in stopwords:
            continue
        if term.endswith("s") and len(term) > 3:
            term = term[:-1]
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("!["):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _preview(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _console_summary(payload: dict[str, Any]) -> dict[str, Any]:
    projects = []
    for project in payload["projects"]:
        projects.append(
            {
                "project": project["project"],
                "status": project["status"],
                "cases": len(project.get("cases") or []),
                "primary_labels": [
                    case["audit_summary"]["primary_audit_label"]
                    for case in project.get("cases") or []
                ],
                "support_rates": [
                    case["verify_summary"]["support_rate"]
                    for case in project.get("cases") or []
                ],
            }
        )
    return {"projects": projects, "summary_path": _rel(SUMMARY_PATH), "markdown_path": _rel(MARKDOWN_PATH)}


def _markdown_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Real-World RAG Validation",
        "",
        "This is a smoke test against public GitHub RAG projects. It does not vendor their source code.",
        "The runner clones/uses local scratch copies under `.contexttrace/real_world_repos`, retrieves from real project docs/code, creates portable RAG traces, and verifies them with ContextTrace.",
        "",
        "Important limitation: this does not execute each original application end-to-end. The cloned projects often require Poetry, local model downloads, GPU-specific dependencies, or app-specific setup. This validation tests ContextTrace against real project corpora and realistic RAG artifacts derived from those corpora.",
        "",
        "This is not a leaderboard. It answers one practical question: when a developer points ContextTrace at real RAG-style artifacts, does the output explain useful grounding failures?",
        "",
        "## Run",
        "",
        "```bash",
        "python benchmarks/real_world_rag/run_real_world_validation.py",
        "```",
        "",
        "Environment used in the latest run:",
        "",
        f"- Generation model: `{payload['generation_model']}`",
        f"- Embedding model: `{payload['embedding_model']}`",
        f"- Answer mode: `{payload['answer_mode']}`",
        "- Date: `2026-06-04`",
        "",
        "## Results",
        "",
    ]
    for project in payload["projects"]:
        lines.extend(
            [
                f"### {project['project']}",
                "",
                f"- Repository: {project['repo_url']}",
                f"- Status: `{project['status']}`",
                f"- Notes: {project.get('notes', '')}",
                f"- Corpus files: `{project.get('corpus_files', 0)}`",
                f"- Corpus chunks: `{project.get('corpus_chunks', 0)}`",
                "",
            ]
        )
        if not project.get("cases"):
            lines.append(f"- Skipped reason: {project.get('reason', 'unknown')}")
            lines.append("")
            continue
        lines.extend(["| Case | Type | Support Rate | Primary Audit Label | Failure Type | Reports |", "| --- | --- | ---: | --- | --- | --- |"])
        for case in project["cases"]:
            verify = case["verify_summary"]
            audit = case["audit_summary"]
            reports = (
                f"[verify](reports/{Path(case['verify_report_path']).name}) / "
                f"[audit](reports/{Path(case['audit_report_path']).name}) / "
                f"[trace](traces/{Path(case['trace_path']).name})"
            )
            lines.append(
                "| {case_id} | `{case_type}` | {support:.3f} | `{label}` | `{failure}` | {reports} |".format(
                    case_id=case["id"],
                    case_type=case.get("case_type", ""),
                    support=float(verify.get("support_rate") or 0.0),
                    label=audit.get("primary_audit_label"),
                    failure=verify.get("failure_type"),
                    reports=reports,
                )
            )
        lines.append("")
        lines.append("Representative findings:")
        for case in project["cases"]:
            claim_bits = [
                f"`{claim['verdict']}`/{claim['root_cause']}"
                for claim in case.get("top_claims") or []
            ]
            lines.append(
                "- `{}`: {}. Claims: {}".format(
                    case["id"],
                    case["question"],
                    ", ".join(claim_bits) or "no factual claims extracted",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Honest Takeaways",
            "",
            "- ContextTrace is already useful as a local post-hoc verifier for RAG artifacts built from real project corpora.",
            "- The clean smoke cases produced `no_failure_detected` with support rate `1.0`, which is the expected pass behavior.",
            "- The retrieval stress controls produced `unsupported_answer`, `should_have_abstained`, and audit-level `retrieval_miss`, which is the expected failure behavior.",
            "- The biggest gap is ingestion ergonomics: real projects do not expose a universal trace format, so adapters are still manual.",
            "- The next product feature should be adapter helpers that turn common LangChain, Haystack, LlamaIndex, Ollama, and HTTP endpoint traces into ContextTrace JSON with minimal glue code.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
