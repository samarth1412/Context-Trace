from __future__ import annotations

import argparse
import ast
import bz2
import hashlib
import json
import random
import shutil
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator


CRAG_REPOSITORY = "https://github.com/facebookresearch/CRAG"
CRAG_REPOSITORY_COMMIT = "ad1518887dd4d9ebcd7de95388c7a62751e7705c"
CRAG_TASK_1_AND_2_V5_FILENAME = "crag_task_1_and_2_dev_v5.jsonl.bz2"
CRAG_TASK_1_AND_2_V5_BYTES = 739_310_088
CRAG_TASK_1_AND_2_V5_SHA256 = "d4c14897d8ea2f450a24e098b595d8247c6575f996f9869d6f27a020fe020618"
CRAG_TASK_1_AND_2_V5_URL = (
    "https://media.githubusercontent.com/media/facebookresearch/CRAG/"
    + CRAG_REPOSITORY_COMMIT
    + "/data/"
    + CRAG_TASK_1_AND_2_V5_FILENAME
)
DEFAULT_STRATIFY_BY = ("domain", "question_type", "static_or_dynamic", "split")
DEFAULT_CONTEXT_CHAR_LIMIT = 12_000


class _VisibleTextParser(HTMLParser):
    _SKIPPED_TAGS = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in self._SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def download_crag_task_1_and_2_v5(output_dir: str | Path) -> str:
    output_path = Path(output_dir) / CRAG_TASK_1_AND_2_V5_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and archive_sha256(output_path) == CRAG_TASK_1_AND_2_V5_SHA256:
        return str(output_path)

    partial_path = output_path.with_name(output_path.name + ".part")
    if partial_path.exists() and partial_path.stat().st_size >= CRAG_TASK_1_AND_2_V5_BYTES:
        if archive_sha256(partial_path) == CRAG_TASK_1_AND_2_V5_SHA256:
            partial_path.replace(output_path)
            return str(output_path)
        partial_path.unlink()
    offset = partial_path.stat().st_size if partial_path.exists() else 0
    request = urllib.request.Request(
        CRAG_TASK_1_AND_2_V5_URL,
        headers={"Range": "bytes=%s-" % offset} if offset else {},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        append = offset > 0 and getattr(response, "status", None) == 206
        mode = "ab" if append else "wb"
        with partial_path.open(mode) as target:
            shutil.copyfileobj(response, target, length=1024 * 1024)

    actual_sha256 = archive_sha256(partial_path)
    if actual_sha256 != CRAG_TASK_1_AND_2_V5_SHA256:
        partial_path.unlink(missing_ok=True)
        raise ValueError(
            "CRAG archive checksum mismatch: expected %s, got %s"
            % (CRAG_TASK_1_AND_2_V5_SHA256, actual_sha256)
        )
    partial_path.replace(output_path)
    return str(output_path)


def archive_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_crag_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    input_path = Path(path)
    handle = (
        bz2.open(input_path, "rt", encoding="utf-8")
        if input_path.suffix.lower() == ".bz2"
        else input_path.open("r", encoding="utf-8")
    )
    with handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid CRAG JSON on line %s." % line_number) from exc
            if not isinstance(row, dict):
                raise ValueError("CRAG line %s must contain a JSON object." % line_number)
            yield row


def adapt_crag_archive(
    path: str | Path,
    *,
    dataset: str = "CRAG-Task1-v5",
    source_name: str = "CRAG Task 1 v5",
    sample_size: int | None = 200,
    sample_seed: int = 13,
    stratify_by: list[str] | tuple[str, ...] = DEFAULT_STRATIFY_BY,
    split: str = "all",
    max_pages: int = 5,
    context_char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT,
    source_sha256: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(str(input_path))
    if split not in {"all", "0", "1"}:
        raise ValueError("split must be one of: all, 0, 1")
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if context_char_limit < 500:
        raise ValueError("context_char_limit must be at least 500")

    metadata_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    skipped = Counter()
    for index, row in enumerate(iter_crag_rows(input_path)):
        interaction_id = str(row.get("interaction_id") or "").strip()
        if not interaction_id:
            skipped["missing_id"] += 1
            continue
        if interaction_id in seen_ids:
            raise ValueError("CRAG interaction IDs must be unique; duplicate: %s" % interaction_id)
        seen_ids.add(interaction_id)
        if split != "all" and str(row.get("split")) != split:
            skipped["split_filtered"] += 1
            continue
        if not str(row.get("query") or "").strip():
            skipped["missing_query"] += 1
            continue
        if _is_missing_answer(row.get("answer")):
            skipped["missing_or_sentinel_answer"] += 1
            continue
        if not isinstance(row.get("search_results"), list) or not row.get("search_results"):
            skipped["missing_search_results"] += 1
            continue
        metadata_rows.append(
            {
                "index": index,
                "interaction_id": interaction_id,
                "domain": str(row.get("domain") or ""),
                "question_type": str(row.get("question_type") or ""),
                "static_or_dynamic": str(row.get("static_or_dynamic") or ""),
                "split": str(row.get("split") if row.get("split") is not None else ""),
            }
        )

    selected_metadata = _select_metadata(
        metadata_rows,
        sample_size=sample_size,
        sample_seed=sample_seed,
        stratify_by=list(stratify_by),
    )
    selected_ids = {item["interaction_id"] for item in selected_metadata}
    adapted_by_id = {}
    for row in iter_crag_rows(input_path):
        interaction_id = str(row.get("interaction_id") or "").strip()
        if interaction_id not in selected_ids:
            continue
        adapted_by_id[interaction_id] = adapt_crag_row(
            row,
            dataset=dataset,
            source_name=source_name,
            max_pages=max_pages,
            context_char_limit=context_char_limit,
        )
    missing_selected_ids = selected_ids.difference(adapted_by_id)
    if missing_selected_ids:
        raise ValueError(
            "Selected CRAG rows disappeared during the second pass: %s"
            % ", ".join(sorted(missing_selected_ids)[:10])
        )
    adapted_rows = [adapted_by_id[item["interaction_id"]] for item in selected_metadata]

    actual_source_digest = archive_sha256(input_path)
    if source_sha256 and source_sha256 != actual_source_digest:
        raise ValueError(
            "Supplied CRAG source SHA256 does not match the archive: expected %s, got %s"
            % (source_sha256, actual_source_digest)
        )
    source_digest = actual_source_digest
    manifest = {
        "adapter": "crag_task1_contexttrace_adapter",
        "adapter_version": 1,
        "dataset": dataset,
        "source_name": source_name,
        "source": {
            "path": str(input_path),
            "sha256": source_digest,
            "bytes": input_path.stat().st_size,
            "matches_official_sha256": source_digest == CRAG_TASK_1_AND_2_V5_SHA256,
            "repository": CRAG_REPOSITORY,
            "repository_commit": CRAG_REPOSITORY_COMMIT,
            "official_url": CRAG_TASK_1_AND_2_V5_URL,
        },
        "sampling": {
            "method": "stratified_round_robin" if stratify_by else "random",
            "sample_size": sample_size,
            "sample_seed": sample_seed,
            "stratify_by": list(stratify_by),
            "split": split,
            "eligible_rows": len(metadata_rows),
            "selected_rows": len(adapted_rows),
            "selected_ids_sha256": _selected_ids_sha256(selected_metadata),
            "selected_distribution": _distribution(selected_metadata),
        },
        "context_extraction": {
            "max_pages": max_pages,
            "context_char_limit_per_page": context_char_limit,
            "html_policy": "visible_text_without_script_style_noscript_template_svg",
        },
        "label_policy": {
            "mode": "unreviewed_gold_answer_proxy",
            "publishable": False,
            "description": (
                "CRAG gold answers establish answer correctness, not whether the supplied web pages "
                "support every answer claim. Rows require independent grounding review or official "
                "judged model responses before verifier failure metrics are publishable."
            ),
        },
        "skipped": dict(sorted(skipped.items())),
    }
    return adapted_rows, manifest


def adapt_crag_row(
    row: dict[str, Any],
    *,
    dataset: str = "CRAG-Task1-v5",
    source_name: str = "CRAG Task 1 v5",
    max_pages: int = 5,
    context_char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT,
) -> dict[str, Any]:
    interaction_id = str(row.get("interaction_id") or "").strip()
    if not interaction_id:
        raise ValueError("CRAG row is missing interaction_id.")
    contexts = []
    for index, page in enumerate((row.get("search_results") or [])[:max_pages]):
        if not isinstance(page, dict):
            continue
        text = _page_text(page, char_limit=context_char_limit)
        if not text:
            continue
        contexts.append(
            {
                "id": "crag_%s_web_%s" % (_slug(interaction_id), index),
                "text": text,
                "metadata": {
                    "page_name": str(page.get("page_name") or ""),
                    "page_url": str(page.get("page_url") or ""),
                    "page_last_modified": str(page.get("page_last_modified") or ""),
                    "retrieval_rank": index + 1,
                },
            }
        )
    if not contexts:
        raise ValueError("CRAG row %s has no usable search-result text." % interaction_id)

    alternatives = _alternative_answers(row.get("alternative_answers") or row.get("alt_ans") or [])
    return {
        "id": interaction_id,
        "source": source_name,
        "query": str(row.get("query") or "").strip(),
        "answer": str(row.get("answer") or "").strip(),
        "contexts": contexts,
        "expected_label": ["no_failure_detected"],
        "expected_primary_root_cause": "no_failure_detected",
        "expected_evidence_spans": [],
        "metadata": {
            "dataset": dataset,
            "crag_interaction_id": interaction_id,
            "crag_query_time": str(row.get("query_time") or ""),
            "crag_domain": str(row.get("domain") or ""),
            "crag_question_type": str(row.get("question_type") or ""),
            "crag_static_or_dynamic": str(row.get("static_or_dynamic") or ""),
            "crag_split": row.get("split"),
            "crag_alternative_answers": alternatives,
            "crag_label_scope": "unreviewed_gold_answer_proxy",
            "crag_requires_grounding_review": True,
        },
    }


def write_jsonl_rows(rows: list[dict[str, Any]], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return str(output_path)


def write_manifest(manifest: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def _select_metadata(
    rows: list[dict[str, Any]],
    *,
    sample_size: int | None,
    sample_seed: int,
    stratify_by: list[str],
) -> list[dict[str, Any]]:
    if sample_size is None or sample_size >= len(rows):
        return list(rows)
    sample_size = max(0, int(sample_size))
    rng = random.Random(sample_seed)
    if not stratify_by:
        return sorted(rng.sample(rows, sample_size), key=lambda item: item["index"])
    buckets: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in stratify_by)
        buckets.setdefault(key, []).append(row)
    selected = []
    keys = sorted(buckets)
    while len(selected) < sample_size and keys:
        progressed = False
        for key in list(keys):
            bucket = buckets[key]
            if not bucket:
                keys.remove(key)
                continue
            selected.append(bucket.pop(rng.randrange(len(bucket))))
            progressed = True
            if len(selected) >= sample_size:
                break
        if not progressed:
            break
    return sorted(selected, key=lambda item: item["index"])


def _distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        field: dict(sorted(Counter(str(row.get(field) or "") for row in rows).items()))
        for field in DEFAULT_STRATIFY_BY
    }


def _selected_ids_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(str(row.get("interaction_id") or "") for row in rows) + ("\n" if rows else "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _page_text(page: dict[str, Any], *, char_limit: int) -> str:
    title = _collapse(page.get("page_name"))
    snippet = _collapse(page.get("page_snippet"))
    parser = _VisibleTextParser()
    try:
        parser.feed(str(page.get("page_result") or ""))
        parser.close()
    except Exception:
        parser.parts = []
    visible = _collapse(" ".join(parser.parts))
    parts = []
    if title:
        parts.append("Page title: %s" % title)
    if snippet:
        parts.append("Snippet: %s" % snippet)
    if visible:
        parts.append("Page text: %s" % visible)
    text = "\n".join(parts)
    if len(text) <= char_limit:
        return text
    return text[: max(1, char_limit - 4)].rsplit(" ", 1)[0].rstrip() + " ..."


def _collapse(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_missing_answer(value: Any) -> bool:
    return _collapse(value).lower() in {"", "n/a", "nan", "none", "null"}


def _alternative_answers(value: Any) -> list[str]:
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                parsed = [text]
    if not isinstance(parsed, (list, tuple, set)):
        parsed = [parsed]
    return [str(item).strip() for item in parsed if str(item).strip()]


def _slug(value: Any) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "case"))
    return "_".join(part for part in text.split("_") if part) or "case"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize the official CRAG Task 1/2 v5 archive into review-pending ContextTrace rows."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Official or compatible CRAG JSONL/JSONL.BZ2 file.")
    source.add_argument("--download-official", action="store_true")
    parser.add_argument("--download-dir", default=str(Path(__file__).with_name("out") / "crag_official"))
    parser.add_argument("--output", required=True, help="Generic external JSONL rows to write.")
    parser.add_argument("--manifest-output", help="Adapter manifest JSON; defaults beside --output.")
    parser.add_argument(
        "--require-official-checksum",
        action="store_true",
        help="Reject --input unless it matches the pinned official CRAG Task 1/2 v5 SHA256.",
    )
    parser.add_argument("--dataset", default="CRAG-Task1-v5")
    parser.add_argument("--source-name", default="CRAG Task 1 v5")
    parser.add_argument("--sample-size", default=200, type=int)
    parser.add_argument("--sample-seed", default=13, type=int)
    parser.add_argument("--stratify-by", default=",".join(DEFAULT_STRATIFY_BY))
    parser.add_argument("--split", choices=["all", "0", "1"], default="all")
    parser.add_argument("--max-pages", default=5, type=int)
    parser.add_argument("--context-char-limit", default=DEFAULT_CONTEXT_CHAR_LIMIT, type=int)
    args = parser.parse_args(argv)

    input_path = (
        download_crag_task_1_and_2_v5(args.download_dir)
        if args.download_official
        else str(args.input)
    )
    digest = archive_sha256(input_path)
    if (args.download_official or args.require_official_checksum) and digest != CRAG_TASK_1_AND_2_V5_SHA256:
        raise ValueError("Official CRAG archive failed checksum verification.")
    rows, manifest = adapt_crag_archive(
        input_path,
        dataset=args.dataset,
        source_name=args.source_name,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        stratify_by=[field.strip() for field in args.stratify_by.split(",") if field.strip()],
        split=args.split,
        max_pages=args.max_pages,
        context_char_limit=args.context_char_limit,
        source_sha256=digest,
    )
    output_path = write_jsonl_rows(rows, args.output)
    manifest_path = args.manifest_output or str(Path(args.output).with_suffix(".manifest.json"))
    write_manifest(manifest, manifest_path)
    print("Wrote: %s" % output_path)
    print("Manifest: %s" % manifest_path)
    print("Input: %s" % input_path)
    print("Rows: %s" % len(rows))
    print("Label scope: unreviewed_gold_answer_proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
