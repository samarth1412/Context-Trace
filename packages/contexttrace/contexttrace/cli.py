from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from contexttrace.evaluator import EvalThresholds, run_evaluation


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "eval":
        return _run_eval_command(args, parser)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contexttrace")
    subparsers = parser.add_subparsers(dest="command")

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run a RAG eval dataset and send traces to ContextTrace.",
    )
    eval_parser.add_argument("--dataset", required=True, help="Path to eval questions JSON.")
    eval_parser.add_argument("--endpoint", required=True, help="RAG API endpoint to call.")
    eval_parser.add_argument(
        "--api-key",
        default=os.getenv("CONTEXTTRACE_API_KEY"),
        help="ContextTrace API key. Defaults to CONTEXTTRACE_API_KEY.",
    )
    eval_parser.add_argument(
        "--project",
        default=os.getenv("CONTEXTTRACE_PROJECT", "ci-rag-eval"),
        help="ContextTrace project name.",
    )
    eval_parser.add_argument(
        "--contexttrace-url",
        default=os.getenv("CONTEXTTRACE_BASE_URL", "http://localhost:8000"),
        help="ContextTrace backend URL.",
    )
    eval_parser.add_argument(
        "--min-citation-support",
        type=float,
        default=float(os.getenv("CONTEXTTRACE_MIN_CITATION_SUPPORT", "0.8")),
        help="Fail when average citation support is below this value.",
    )
    eval_parser.add_argument(
        "--max-unsupported-claim-rate",
        type=float,
        default=float(os.getenv("CONTEXTTRACE_MAX_UNSUPPORTED_CLAIM_RATE", "0.1")),
        help="Fail when average unsupported claim rate is above this value.",
    )
    eval_parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=float(os.getenv("CONTEXTTRACE_MAX_FAILURE_RATE", "0.0")),
        help="Fail when failure rate is above this value.",
    )
    eval_parser.add_argument(
        "--summary-path",
        default=os.getenv("CONTEXTTRACE_EVAL_SUMMARY_PATH", "contexttrace-eval-summary.md"),
        help="Markdown summary output path.",
    )
    eval_parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("CONTEXTTRACE_EVAL_TIMEOUT", "30")),
        help="Per-request timeout in seconds.",
    )
    eval_parser.add_argument(
        "--endpoint-header",
        action="append",
        default=[],
        help="Header for the RAG endpoint, formatted as Name:Value. May be repeated.",
    )
    return parser


def _run_eval_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.api_key:
        parser.error("--api-key or CONTEXTTRACE_API_KEY is required")

    try:
        summary = run_evaluation(
            dataset_path=args.dataset,
            endpoint=args.endpoint,
            api_key=args.api_key,
            project=args.project,
            base_url=args.contexttrace_url,
            thresholds=EvalThresholds(
                min_citation_support=args.min_citation_support,
                max_unsupported_claim_rate=args.max_unsupported_claim_rate,
                max_failure_rate=args.max_failure_rate,
            ),
            summary_path=args.summary_path,
            timeout=args.timeout,
            endpoint_headers=_parse_headers(args.endpoint_header),
        )
    except Exception as exc:
        print("ContextTrace eval failed to run: %s" % exc, file=sys.stderr)
        return 2

    print(summary.markdown)
    return 1 if summary.failed else 0


def _parse_headers(values: list[str]) -> dict[str, str]:
    headers = {}
    for value in values:
        if ":" not in value:
            raise ValueError("Endpoint headers must be formatted as Name:Value.")
        name, header_value = value.split(":", 1)
        headers[name.strip()] = header_value.strip()
    return headers


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
