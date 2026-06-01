from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from contexttrace._version import __version__
from contexttrace.client import ContextTrace
from contexttrace.config import load_config, write_default_config
from contexttrace.errors import ContextTraceError
from contexttrace.evaluator import EvalThresholds, run_evaluation


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init_command(args)

    if args.command == "config" and args.config_command == "show":
        return _run_config_show_command(args)

    if args.command == "trace" and args.trace_command == "list":
        return _run_trace_list_command(args)

    if args.command == "report":
        return _run_report_command(args, parser)

    if args.command == "eval":
        return _run_eval_command(args, parser)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contexttrace")
    parser.add_argument(
        "--version",
        action="version",
        version="contexttrace %s" % __version__,
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to contexttrace.yaml. Defaults to ./contexttrace.yaml when present.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Create a local contexttrace.yaml configuration file.",
    )
    init_parser.add_argument("--path", default="contexttrace.yaml", help="Configuration file to write.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite an existing config file.")

    trace_parser = subparsers.add_parser("trace", help="Inspect local traces.")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command")
    trace_list_parser = trace_subparsers.add_parser("list", help="List recent traces.")
    trace_list_parser.add_argument("--limit", type=int, default=20, help="Maximum traces to show.")

    report_parser = subparsers.add_parser("report", help="Export a local HTML report.")
    report_parser.add_argument("--last", action="store_true", help="Export the most recent trace.")
    report_parser.add_argument("--trace-id", default=None, help="Trace ID to export.")
    report_parser.add_argument("--output", default="report.html", help="HTML file to write.")

    config_parser = subparsers.add_parser("config", help="Inspect SDK configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_show_parser = config_subparsers.add_parser("show", help="Show resolved configuration.")
    config_show_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Show API keys instead of masking them.",
    )

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run a RAG eval dataset and send traces to ContextTrace.",
    )
    eval_parser.add_argument("--dataset", required=True, help="Path to eval questions JSON.")
    eval_parser.add_argument(
        "--endpoint",
        default=None,
        help="RAG API endpoint to call. Defaults to config eval_endpoint or CONTEXTTRACE_EVAL_ENDPOINT.",
    )
    eval_parser.add_argument(
        "--api-key",
        default=None,
        help="ContextTrace API key. Defaults to CONTEXTTRACE_API_KEY.",
    )
    eval_parser.add_argument(
        "--project",
        default=None,
        help="ContextTrace project name.",
    )
    eval_parser.add_argument(
        "--contexttrace-url",
        default=None,
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


def _run_init_command(args: argparse.Namespace) -> int:
    path = write_default_config(args.path, overwrite=args.force)
    config = load_config(config_path=path)
    Path(config.local_store_dir).mkdir(parents=True, exist_ok=True)
    print("Wrote %s" % path)
    print("Local trace store: %s" % config.local_store_dir)
    return 0


def _run_config_show_command(args: argparse.Namespace) -> int:
    config = load_config(config_path=args.config)
    payload = asdict(config)
    if payload.get("api_key") and not args.show_secrets:
        payload["api_key"] = _mask_secret(str(payload["api_key"]))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _run_trace_list_command(args: argparse.Namespace) -> int:
    try:
        client = ContextTrace(config_path=args.config)
        traces = client.list_traces(limit=args.limit)
    except Exception as exc:
        print("ContextTrace trace list failed: %s" % exc, file=sys.stderr)
        return 2

    if not traces:
        print("No traces found.")
        return 0

    for trace in traces:
        print(
            "{trace_id}\t{status}\t{query}".format(
                trace_id=trace.get("id") or trace.get("trace_id"),
                status=trace.get("status") or "unknown",
                query=(trace.get("query") or "").replace("\n", " ")[:100],
            )
        )
    return 0


def _run_report_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.last and not args.trace_id:
        parser.error("report requires --last or --trace-id")
    try:
        client = ContextTrace(config_path=args.config)
        output = client.export_report(trace_id=args.trace_id, path=args.output, last=args.last)
    except Exception as exc:
        print("ContextTrace report failed: %s" % exc, file=sys.stderr)
        return 2

    print("Wrote %s" % output)
    return 0


def _run_eval_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    config = load_config(
        api_key=args.api_key,
        project=args.project,
        base_url=args.contexttrace_url,
        config_path=args.config,
    )
    endpoint = args.endpoint or config.eval_endpoint
    if not endpoint:
        parser.error("--endpoint or eval_endpoint in contexttrace.yaml is required")
    if config.mode != "local" and not config.api_key:
        parser.error("--api-key or CONTEXTTRACE_API_KEY is required")

    client = None
    try:
        client = ContextTrace(
            api_key=config.api_key,
            project=config.project,
            base_url=config.base_url,
            mode=config.mode,
            timeout=args.timeout,
            retries=config.retries,
            debug=config.debug,
            local_store_dir=config.local_store_dir,
        )
        summary = run_evaluation(
            dataset_path=args.dataset,
            endpoint=endpoint,
            api_key=config.api_key or "",
            project=config.project,
            base_url=config.base_url,
            thresholds=EvalThresholds(
                min_citation_support=args.min_citation_support,
                max_unsupported_claim_rate=args.max_unsupported_claim_rate,
                max_failure_rate=args.max_failure_rate,
            ),
            summary_path=args.summary_path,
            timeout=args.timeout,
            endpoint_headers=_parse_headers(args.endpoint_header),
            contexttrace=client,
        )
    except ContextTraceError as exc:
        print("ContextTrace eval failed to run: %s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print("ContextTrace eval failed to run: %s" % exc, file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()

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


def _mask_secret(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return "%s***%s" % (value[:3], value[-3:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
