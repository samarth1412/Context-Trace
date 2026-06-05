from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
DEFAULT_HASH_DIMENSIONS = 2048


class LocalMLError(RuntimeError):
    """Raised when an explicitly configured local ML backend cannot run."""


def local_ml_similarity(left: str, right: str) -> float:
    """Return a deterministic local similarity score in [0, 1]."""

    model_path = os.getenv("CONTEXTTRACE_LOCAL_ML_MODEL_PATH")
    if model_path:
        return _sentence_transformer_similarity(left, right, model_path=model_path)
    return _hash_similarity(left, right)


def local_ml_score_pair(
    claim_text: str,
    evidence_text: str,
    *,
    lexical_score: float,
) -> float:
    """Blend existing semantic evidence score with local embedding similarity."""

    similarity = local_ml_similarity(claim_text, evidence_text)
    blended = (0.58 * lexical_score) + (0.42 * similarity)
    return round(max(lexical_score, min(1.0, blended)), 3)


def _hash_similarity(left: str, right: str) -> float:
    left_vector = _hash_vector(left)
    right_vector = _hash_vector(right)
    if not left_vector or not right_vector:
        return 0.0
    dot = sum(value * right_vector.get(index, 0.0) for index, value in left_vector.items())
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    if not left_norm or not right_norm:
        return 0.0
    return round(max(0.0, min(1.0, dot / (left_norm * right_norm))), 3)


def _hash_vector(text: str, *, dimensions: int = DEFAULT_HASH_DIMENSIONS) -> dict[int, float]:
    features = _features(text)
    vector: dict[int, float] = {}
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[-1] % 2 == 0 else -1.0
        vector[bucket] = vector.get(bucket, 0.0) + sign
    return vector


def _features(text: str) -> list[str]:
    normalized = str(text or "").lower()
    tokens = [
        token.strip("._-/")
        for token in TOKEN_RE.findall(normalized)
        if token.strip("._-/")
    ]
    features: list[str] = []
    features.extend("tok:%s" % token for token in tokens)
    features.extend("bi:%s_%s" % (tokens[index], tokens[index + 1]) for index in range(len(tokens) - 1))
    compact = " ".join(tokens)
    for index in range(max(0, len(compact) - 4)):
        features.append("char:%s" % compact[index : index + 5])
    return features


def _sentence_transformer_similarity(left: str, right: str, *, model_path: str) -> float:
    path = Path(model_path)
    if not path.exists():
        raise LocalMLError(
            "CONTEXTTRACE_LOCAL_ML_MODEL_PATH must point to an existing local model directory or file."
        )
    model = _load_sentence_transformer(str(path))
    embeddings = model.encode([left, right], normalize_embeddings=True)
    score = _dot(embeddings[0], embeddings[1])
    return round(max(0.0, min(1.0, float(score))), 3)


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_path: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise LocalMLError(
            "Install contexttrace[local-ml] to use a local SentenceTransformers model."
        ) from exc

    try:
        return SentenceTransformer(model_path, local_files_only=True)
    except TypeError:
        return SentenceTransformer(model_path)


def _dot(left: Any, right: Any) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right))
