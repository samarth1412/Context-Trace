from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import TraceContext


DEFAULT_NLI_BACKEND = "auto"
DEFAULT_NLI_MAX_LENGTH = 512


class LocalNLIError(RuntimeError):
    """Raised when an explicitly configured local NLI backend cannot run."""


@dataclass(frozen=True)
class NLIResult:
    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    backend: str = "local_nli"
    model_path: str | None = None


class LocalNLIJudge:
    """Local claim+span NLI verifier.

    The provider only sees selected evidence spans, not the full answer prose.
    """

    provider = "local_nli"

    def __init__(
        self,
        *,
        model_path: str | None = None,
        tokenizer_path: str | None = None,
        backend: str | None = None,
        max_length: int = DEFAULT_NLI_MAX_LENGTH,
        classifier: Callable[[str, str], NLIResult] | None = None,
    ) -> None:
        self.model_path = model_path or os.getenv("CONTEXTTRACE_NLI_MODEL_PATH") or ""
        self.tokenizer_path = tokenizer_path or os.getenv("CONTEXTTRACE_NLI_TOKENIZER_PATH") or None
        self.backend = _normalize_backend(backend or os.getenv("CONTEXTTRACE_NLI_BACKEND") or DEFAULT_NLI_BACKEND)
        self.max_length = max_length
        self._classifier = classifier
        self.model = Path(self.model_path).name if self.model_path else None
        if self._classifier is None:
            _validate_model_path(self.model_path)

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        del query
        if not contexts:
            return JudgeVerdict(
                verdict="unsupported",
                confidence=0.95,
                reason="No selected evidence span was available for local NLI.",
                missing_facts=[claim],
                provider=self.provider,
                model=self.model,
                raw={"evidence_scope": "selected_evidence_spans_only"},
            )

        results: list[tuple[TraceContext, NLIResult]] = []
        for context in contexts:
            result = self._classify(context.text, claim)
            results.append((context, result))
        context, result = _choose_result(results)
        return _to_judge_verdict(
            claim=claim,
            context=context,
            result=result,
            model=self.model,
        )

    def _classify(self, premise: str, hypothesis: str) -> NLIResult:
        if self._classifier is not None:
            return self._classifier(premise, hypothesis)
        return local_nli_entailment(
            premise=premise,
            hypothesis=hypothesis,
            model_path=self.model_path,
            tokenizer_path=self.tokenizer_path,
            backend=self.backend,
            max_length=self.max_length,
        )


def build_nli_provider(
    *,
    model_path: str | None = None,
    tokenizer_path: str | None = None,
    backend: str | None = None,
    max_length: int = DEFAULT_NLI_MAX_LENGTH,
) -> LocalNLIJudge | None:
    resolved_model_path = model_path or os.getenv("CONTEXTTRACE_NLI_MODEL_PATH")
    if not resolved_model_path:
        return None
    return LocalNLIJudge(
        model_path=resolved_model_path,
        tokenizer_path=tokenizer_path,
        backend=backend,
        max_length=max_length,
    )


def local_nli_entailment(
    *,
    premise: str,
    hypothesis: str,
    model_path: str,
    tokenizer_path: str | None = None,
    backend: str = DEFAULT_NLI_BACKEND,
    max_length: int = DEFAULT_NLI_MAX_LENGTH,
) -> NLIResult:
    path = _validate_model_path(model_path)
    resolved_backend = _resolve_backend(path, backend)
    if resolved_backend == "onnx":
        return _onnx_entailment(
            premise=premise,
            hypothesis=hypothesis,
            model_path=path,
            tokenizer_path=tokenizer_path,
            max_length=max_length,
        )
    if resolved_backend == "transformers":
        return _transformers_entailment(
            premise=premise,
            hypothesis=hypothesis,
            model_path=path,
            tokenizer_path=tokenizer_path,
            max_length=max_length,
        )
    raise LocalNLIError("Unsupported local NLI backend: %s" % backend)


def _transformers_entailment(
    *,
    premise: str,
    hypothesis: str,
    model_path: Path,
    tokenizer_path: str | None,
    max_length: int,
) -> NLIResult:
    tokenizer, model, torch_module, id2label = _load_transformers_model(str(model_path), tokenizer_path or str(model_path))
    encoded = tokenizer(
        premise,
        hypothesis,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
    )
    with torch_module.no_grad():
        output = model(**encoded)
        logits = output.logits[0]
        probabilities = torch_module.softmax(logits, dim=-1).tolist()
    return _result_from_probabilities(
        probabilities,
        id2label=id2label,
        backend="transformers",
        model_path=str(model_path),
    )


def _onnx_entailment(
    *,
    premise: str,
    hypothesis: str,
    model_path: Path,
    tokenizer_path: str | None,
    max_length: int,
) -> NLIResult:
    tokenizer, session, input_names, id2label, numpy_module, onnx_path = _load_onnx_model(
        str(model_path),
        tokenizer_path or str(model_path if model_path.is_dir() else model_path.parent),
    )
    encoded = tokenizer(
        premise,
        hypothesis,
        return_tensors="np",
        truncation=True,
        max_length=max_length,
    )
    inputs = {
        name: encoded[name]
        for name in input_names
        if name in encoded
    }
    if not inputs:
        raise LocalNLIError("ONNX NLI tokenizer did not produce any model inputs.")
    logits = session.run(None, inputs)[0][0]
    shifted = logits - numpy_module.max(logits)
    exp_values = numpy_module.exp(shifted)
    probabilities = (exp_values / numpy_module.sum(exp_values)).tolist()
    return _result_from_probabilities(
        probabilities,
        id2label=id2label,
        backend="onnx",
        model_path=str(onnx_path),
    )


@lru_cache(maxsize=2)
def _load_transformers_model(model_path: str, tokenizer_path: str) -> tuple[Any, Any, Any, dict[int, str]]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise LocalNLIError(
            "Install contexttrace[nli] to use a local Transformers NLI model."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
    model.eval()
    id2label = _id2label(getattr(getattr(model, "config", None), "id2label", None))
    return tokenizer, model, torch, id2label


@lru_cache(maxsize=2)
def _load_onnx_model(model_path: str, tokenizer_path: str) -> tuple[Any, Any, list[str], dict[int, str], Any, Path]:
    try:
        import numpy
        import onnxruntime
        from transformers import AutoConfig, AutoTokenizer
    except ImportError as exc:
        raise LocalNLIError(
            "Install contexttrace[nli-onnx] to use a local ONNX NLI model."
        ) from exc

    onnx_path = _resolve_onnx_path(Path(model_path))
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    try:
        config = AutoConfig.from_pretrained(tokenizer_path, local_files_only=True)
        id2label = _id2label(getattr(config, "id2label", None))
    except Exception:
        id2label = {}
    session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_names = [item.name for item in session.get_inputs()]
    return tokenizer, session, input_names, id2label, numpy, onnx_path


def _result_from_probabilities(
    probabilities: list[float],
    *,
    id2label: dict[int, str],
    backend: str,
    model_path: str,
) -> NLIResult:
    scores = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}
    total = len(probabilities)
    for index, probability in enumerate(probabilities):
        canonical = _canonical_label(id2label.get(index, ""), index=index, total=total)
        scores[canonical] = max(scores.get(canonical, 0.0), float(probability))
    label = max(scores, key=lambda key: scores[key])
    return NLIResult(
        label=label,
        confidence=round(float(scores[label]), 3),
        scores={key: round(float(value), 3) for key, value in scores.items()},
        backend=backend,
        model_path=model_path,
    )


def _choose_result(results: list[tuple[TraceContext, NLIResult]]) -> tuple[TraceContext, NLIResult]:
    entailments = [item for item in results if item[1].label == "entailment"]
    contradictions = [item for item in results if item[1].label == "contradiction"]
    if entailments:
        best_entailment = max(entailments, key=lambda item: item[1].confidence)
        best_contradiction = max(contradictions, key=lambda item: item[1].confidence) if contradictions else None
        if best_contradiction and best_contradiction[1].confidence > best_entailment[1].confidence + 0.08:
            return best_contradiction
        return best_entailment
    if contradictions:
        return max(contradictions, key=lambda item: item[1].confidence)
    return max(results, key=lambda item: item[1].confidence)


def _to_judge_verdict(
    *,
    claim: str,
    context: TraceContext,
    result: NLIResult,
    model: str | None,
) -> JudgeVerdict:
    if result.label == "entailment":
        verdict = "supported"
        matched_facts = [claim]
        missing_facts: list[str] = []
        conflicting_facts: list[str] = []
        reason = "Local NLI says the selected evidence span entails the claim."
    elif result.label == "contradiction":
        verdict = "contradicted"
        matched_facts = []
        missing_facts = []
        conflicting_facts = [claim]
        reason = "Local NLI says the selected evidence span contradicts the claim."
    else:
        verdict = "unsupported" if result.confidence >= 0.55 else "unverifiable"
        matched_facts = []
        missing_facts = [claim]
        conflicting_facts = []
        reason = "Local NLI says the selected evidence span does not entail the claim."

    return JudgeVerdict(
        verdict=verdict,
        confidence=result.confidence,
        reason=reason,
        matched_facts=matched_facts,
        missing_facts=missing_facts,
        conflicting_facts=conflicting_facts,
        provider="local_nli",
        model=model,
        raw={
            "nli_label": result.label,
            "nli_scores": dict(result.scores),
            "backend": result.backend,
            "evidence_scope": "selected_evidence_spans_only",
            "context_id": context.id,
            "context_metadata": dict(context.metadata),
        },
    )


def _canonical_label(label: str, *, index: int, total: int) -> str:
    normalized = str(label or "").strip().lower().replace("-", "_")
    if "not_entail" in normalized or "non_entail" in normalized:
        return "neutral"
    if "entail" in normalized:
        return "entailment"
    if "contrad" in normalized:
        return "contradiction"
    if "neutral" in normalized:
        return "neutral"
    if total == 3:
        return ["contradiction", "neutral", "entailment"][min(index, 2)]
    if total == 2:
        return "contradiction" if index == 0 else "entailment"
    return "neutral"


def _id2label(value: Any) -> dict[int, str]:
    if not isinstance(value, dict):
        return {}
    labels: dict[int, str] = {}
    for key, label in value.items():
        try:
            labels[int(key)] = str(label)
        except (TypeError, ValueError):
            continue
    return labels


def _validate_model_path(model_path: str | None) -> Path:
    if not model_path:
        raise LocalNLIError(
            "mode='nli' requires CONTEXTTRACE_NLI_MODEL_PATH or a LocalNLIJudge provider. "
            "ContextTrace never downloads NLI models automatically."
        )
    path = Path(model_path)
    if not path.exists():
        raise LocalNLIError(
            "CONTEXTTRACE_NLI_MODEL_PATH must point to an existing local model directory or ONNX file."
        )
    return path


def _resolve_backend(path: Path, backend: str) -> str:
    normalized = _normalize_backend(backend)
    if normalized != "auto":
        return normalized
    if path.is_file() and path.suffix.lower() == ".onnx":
        return "onnx"
    if path.is_dir() and _resolve_onnx_path(path, required=False) is not None:
        return "onnx"
    return "transformers"


def _resolve_onnx_path(path: Path, *, required: bool = True) -> Path | None:
    if path.is_file() and path.suffix.lower() == ".onnx":
        return path
    if path.is_dir():
        candidates = [
            path / "model.onnx",
            path / "onnx" / "model.onnx",
        ]
        candidates.extend(sorted(path.glob("*.onnx")))
        for candidate in candidates:
            if candidate.exists():
                return candidate
    if required:
        raise LocalNLIError("Local ONNX NLI backend requires a .onnx model file.")
    return None


def _normalize_backend(value: str) -> str:
    backend = str(value or DEFAULT_NLI_BACKEND).strip().lower().replace("-", "_")
    aliases = {
        "hf": "transformers",
        "huggingface": "transformers",
        "torch": "transformers",
        "ort": "onnx",
    }
    backend = aliases.get(backend, backend)
    if backend not in {"auto", "transformers", "onnx"}:
        raise LocalNLIError("CONTEXTTRACE_NLI_BACKEND must be auto, transformers, or onnx.")
    return backend
