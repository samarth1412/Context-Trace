from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedDocument:
    filename: str
    content_type: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    def parse(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> ParsedDocument:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        normalized_type = content_type or _content_type_for_extension(extension)

        if extension == "pdf" or normalized_type == "application/pdf":
            text = self._parse_pdf(content)
        elif extension in {"md", "markdown"} or normalized_type in {
            "text/markdown",
            "text/x-markdown",
        }:
            text = self._parse_text(content)
        elif extension == "txt" or normalized_type.startswith("text/"):
            text = self._parse_text(content)
        else:
            raise ValueError("Unsupported document type. Upload PDF, TXT, or Markdown.")

        return ParsedDocument(
            filename=filename,
            content_type=normalized_type,
            text=_normalize_text(text),
            metadata={"filename": filename, "content_type": normalized_type},
        )

    def _parse_text(self, content: bytes) -> str:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    def _parse_pdf(self, content: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ValueError("PDF parsing requires pypdf.") from exc

        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)


class TokenAwareChunker:
    def __init__(self, *, max_tokens: int = 220, overlap_tokens: int = 40) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive.")
        if overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative.")
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens.")

        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        tokens = _tokenize(document.text)
        if not tokens:
            return []

        chunks: List[DocumentChunk] = []
        start = 0
        index = 0
        step = self.max_tokens - self.overlap_tokens

        while start < len(tokens):
            end = min(start + self.max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            content = _untokenize(chunk_tokens)
            chunks.append(
                DocumentChunk(
                    chunk_id="%s_chunk_%04d" % (_safe_id(document.filename), index),
                    content=content,
                    source=document.filename,
                    metadata={
                        **document.metadata,
                        "chunk_index": index,
                        "token_start": start,
                        "token_end": end,
                        "token_count": len(chunk_tokens),
                    },
                )
            )
            if end == len(tokens):
                break
            start += step
            index += 1

        return chunks


TOKEN_RE = re.compile(r"\S+")


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text)


def _untokenize(tokens: List[str]) -> str:
    return " ".join(tokens).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return cleaned or "document"


def _content_type_for_extension(extension: str) -> str:
    if extension == "pdf":
        return "application/pdf"
    if extension in {"md", "markdown"}:
        return "text/markdown"
    return "text/plain"
