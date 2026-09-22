"""Train and run a local WiCE completeness classifier over selected evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import _wice_cases
from benchmarks.jev_v2_verification.run import shared_input


TRAIN_SHA256 = "3ef74c7203e1d9b369cb2c145e764d8ab4743f008f9765fa47f9bdd6ffa2d2e1"
ENCODER_ID = "sentence-transformers/all-MiniLM-L6-v2"
ENCODER_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
RANDOM_SEED = 20260923
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "his",
    "her",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}
SCALAR_FEATURES = (
    "maximum_cosine",
    "mean_cosine",
    "top_two_cosine_mean",
    "content_token_coverage",
    "bigram_coverage",
    "number_coverage",
    "capitalized_token_coverage",
    "minimum_clause_coverage",
    "selected_span_fraction",
    "selected_character_log",
)


class LocalCompletenessError(RuntimeError):
    """Raised when local completeness training or inference cannot be reproduced."""


def train_model(
    train_path: str | Path,
    *,
    encoder_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise LocalCompletenessError(
            "numpy, sentence-transformers, and scikit-learn are required."
        ) from exc
    source = Path(train_path)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != TRAIN_SHA256:
        raise LocalCompletenessError(
            "WiCE train sha256 %s does not match %s." % (source_hash, TRAIN_SHA256)
        )
    cases = [
        row
        for row in _wice_cases(source)
        if row["expected_verdict"] in {"supported", "partially_supported"}
        and shared_input(row)[0]
    ]
    encoder = SentenceTransformer(str(encoder_path), device="cpu")
    inputs = [_case_input(case) for case in cases]
    matrix = _feature_matrix(inputs, encoder=encoder)
    targets = np.asarray([case["expected_verdict"] == "supported" for case in cases], dtype=int)
    estimator = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=0.1,
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_SEED,
            solver="lbfgs",
        ),
    )
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    out_of_fold = cross_val_predict(
        estimator, matrix, targets, cv=folds, method="predict_proba"
    )[:, 1]
    estimator.fit(matrix, targets)
    scaler = estimator.named_steps["standardscaler"]
    logistic = estimator.named_steps["logisticregression"]
    model = {
        "schema_version": "local-completeness-model-1.0",
        "training_source": {
            "dataset": "WiCE",
            "split": "train",
            "sha256": source_hash,
            "cases": len(cases),
            "supported": int(targets.sum()),
            "partially_supported": int(len(targets) - targets.sum()),
        },
        "encoder": {
            "id": ENCODER_ID,
            "revision": ENCODER_REVISION,
            "embedding_dimension": int(encoder.get_embedding_dimension()),
            "normalize_embeddings": True,
        },
        "feature_layout": {
            "dense_blocks": [
                "absolute_claim_minus_best_evidence",
                "claim_times_best_evidence",
                "absolute_claim_minus_mean_evidence",
                "claim_times_mean_evidence",
            ],
            "scalar_features": list(SCALAR_FEATURES),
            "dimensions": int(matrix.shape[1]),
        },
        "standard_scaler": {
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
        },
        "logistic_regression": {
            "solver": "lbfgs",
            "C": 0.1,
            "class_weight": "balanced",
            "random_seed": RANDOM_SEED,
            "coefficients": [float(value) for value in logistic.coef_[0]],
            "intercept": float(logistic.intercept_[0]),
        },
    }
    model_id = hashlib.sha256(
        json.dumps(model, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    artifact = {"model_id": model_id, **model}
    report = {
        "schema_version": "local-completeness-training-report-1.0",
        "model_id": model_id,
        "five_fold_out_of_fold": {
            "roc_auc": round(float(roc_auc_score(targets, out_of_fold)), 4),
            "average_precision": round(float(average_precision_score(targets, out_of_fold)), 4),
        },
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    return artifact, report


def augment_result(
    result: dict[str, Any],
    model: dict[str, Any],
    *,
    encoder_path: str | Path,
) -> dict[str, Any]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise LocalCompletenessError("sentence-transformers is required.") from exc
    rows = json.loads(json.dumps(result.get("rows") or []))
    encoder = SentenceTransformer(str(encoder_path), device="cpu")
    expected_dimension = int(model["encoder"]["embedding_dimension"])
    if int(encoder.get_embedding_dimension()) != expected_dimension:
        raise LocalCompletenessError("Encoder embedding dimension does not match model artifact.")
    inputs = [row["input_audit"]["exact_shared_input"] for row in rows]
    matrix = _feature_matrix(inputs, encoder=encoder)
    scores = _predict(matrix, model)
    for row, score in zip(rows, scores, strict=True):
        row["signals"]["local_support_probability"] = round(float(score), 8)
        row["signals"]["local_support_model_id"] = model["model_id"]
    return {
        **{key: value for key, value in result.items() if key != "rows"},
        "schema_version": "jev-local-completeness-signals-1.0",
        "local_support_model_id": model["model_id"],
        "local_runtime_network_used": False,
        "rows": rows,
    }


def _case_input(case: dict[str, Any]) -> dict[str, Any]:
    contexts, _ = shared_input(case)
    return {
        "claim": str(case["claim"]),
        "selected_evidence": [{"id": item.id, "text": item.text} for item in contexts],
    }


def _feature_matrix(inputs: list[dict[str, Any]], *, encoder: object) -> Any:
    import numpy as np

    texts = []
    for item in inputs:
        texts.append(str(item["claim"]))
        texts.extend(str(value["text"]) for value in item["selected_evidence"])
    unique_texts = list(dict.fromkeys(texts))
    embeddings = encoder.encode(  # type: ignore[attr-defined]
        unique_texts,
        batch_size=64,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    by_text = dict(zip(unique_texts, embeddings, strict=True))
    vectors = []
    for item in inputs:
        claim_text = str(item["claim"])
        evidence_texts = [str(value["text"]) for value in item["selected_evidence"]]
        if not evidence_texts:
            raise LocalCompletenessError("A case has no selected evidence.")
        claim = by_text[claim_text]
        evidence = np.asarray([by_text[text] for text in evidence_texts])
        cosine = evidence @ claim
        best = evidence[int(np.argmax(cosine))]
        mean = evidence.mean(axis=0)
        scalars = _scalar_features(claim_text, evidence_texts, cosine)
        vectors.append(
            np.concatenate(
                [
                    np.abs(claim - best),
                    claim * best,
                    np.abs(claim - mean),
                    claim * mean,
                    np.asarray(scalars, dtype=float),
                ]
            )
        )
    return np.asarray(vectors)


def _scalar_features(claim: str, evidence: list[str], cosine: Any) -> list[float]:
    claim_tokens = _tokens(claim)
    evidence_text = " ".join(evidence)
    evidence_tokens = _tokens(evidence_text)
    evidence_set = set(evidence_tokens)
    content = [token for token in claim_tokens if len(token) >= 3 and token not in STOPWORDS]
    bigrams = list(zip(claim_tokens, claim_tokens[1:]))
    evidence_bigrams = set(zip(evidence_tokens, evidence_tokens[1:]))
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", claim)
    capitalized = [
        value.casefold()
        for value in re.findall(r"\b[A-Z][A-Za-z0-9-]+\b", claim)
        if value.casefold() not in {"a", "an", "the"}
    ]
    clauses = [
        value
        for value in re.split(r"[,;:]|\b(?:and|but|while|whereas)\b", claim, flags=re.I)
        if value.strip()
    ]
    clause_coverage = []
    for clause in clauses:
        tokens = [
            token for token in _tokens(clause) if len(token) >= 3 and token not in STOPWORDS
        ]
        clause_coverage.append(_coverage(tokens, evidence_set))
    ordered_cosine = sorted((float(value) for value in cosine), reverse=True)
    return [
        ordered_cosine[0],
        sum(ordered_cosine) / len(ordered_cosine),
        sum(ordered_cosine[:2]) / min(2, len(ordered_cosine)),
        _coverage(content, evidence_set),
        _coverage(bigrams, evidence_bigrams),
        _coverage([value.casefold() for value in numbers], evidence_set),
        _coverage(capitalized, evidence_set),
        min(clause_coverage) if clause_coverage else 1.0,
        len(evidence) / 8.0,
        math.log1p(sum(len(value) for value in evidence)) / 10.0,
    ]


def _coverage(values: list[Any], evidence: set[Any]) -> float:
    return sum(value in evidence for value in values) / len(values) if values else 1.0


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _predict(matrix: Any, model: dict[str, Any]) -> list[float]:
    import numpy as np

    means = np.asarray(model["standard_scaler"]["mean"], dtype=float)
    scales = np.asarray(model["standard_scaler"]["scale"], dtype=float)
    coefficients = np.asarray(model["logistic_regression"]["coefficients"], dtype=float)
    intercept = float(model["logistic_regression"]["intercept"])
    if matrix.shape[1] != len(means) or len(means) != len(scales) or len(scales) != len(
        coefficients
    ):
        raise LocalCompletenessError("Local model feature dimensions do not match.")
    logits = ((matrix - means) / scales) @ coefficients + intercept
    return [
        1.0 / (1.0 + math.exp(-float(value)))
        if value >= 0
        else math.exp(float(value)) / (1.0 + math.exp(float(value)))
        for value in logits
    ]


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    train = subparsers.add_parser("train")
    train.add_argument("--train-source", required=True)
    train.add_argument("--encoder-path", required=True)
    train.add_argument("--model-output", required=True)
    train.add_argument("--report-output", required=True)
    augment = subparsers.add_parser("augment")
    augment.add_argument("--result", required=True)
    augment.add_argument("--model", required=True)
    augment.add_argument("--encoder-path", required=True)
    augment.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "train":
        model, report = train_model(args.train_source, encoder_path=args.encoder_path)
        _write(Path(args.model_output), model)
        _write(Path(args.report_output), report)
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        model = json.loads(Path(args.model).read_text(encoding="utf-8"))
        augmented = augment_result(result, model, encoder_path=args.encoder_path)
        _write(Path(args.output), augmented)
        print(json.dumps({"cases": len(augmented["rows"]), "model_id": model["model_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
