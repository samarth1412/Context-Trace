from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import click

from contexttrace._version import __version__
from contexttrace.client import ContextTrace
from contexttrace.config import ContextTraceConfig, load_config, write_default_config
from contexttrace.demo import run_demo_dataset
from contexttrace.demo_data import list_demo_datasets
from contexttrace.endpoint_eval import run_endpoint_eval
from contexttrace.errors import ContextTraceError
from contexttrace.regression import BENCHMARK_STRATEGIES, run_local_benchmark
from contexttrace.report import ReportGenerator
from contexttrace.storage import SQLiteTraceStore
from contexttrace.thresholds import parse_thresholds, threshold_failures
from contexttrace.verify import (
    VerificationInputError,
    list_verify_demos,
    load_trace_file,
    load_verify_demo,
    verify_trace,
)
from contexttrace.verify.benchmark import run_verify_benchmark, write_verify_benchmark_report
from contexttrace.verify.report import VerifyReportGenerator
from contexttrace.viewer import serve_viewer


SAMPLE_QUESTIONS = [
    {
        "id": "refund_policy",
        "query": "What is the refund policy?",
        "expected_sources": ["refund_policy.md"],
    }
]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--config", "config_path", default=None, help="Path to contexttrace.yaml.")
@click.version_option(version=__version__, prog_name="contexttrace")
@click.pass_context
def cli(ctx: click.Context, config_path: Optional[str]) -> None:
    ctx.obj = {"config_path": config_path}


@cli.command()
@click.option("--path", default="contexttrace.yaml", help="Configuration file to write.")
@click.option("--force", is_flag=True, help="Overwrite an existing config file.")
def init(path: str, force: bool) -> None:
    config_path = write_default_config(path, overwrite=force)
    config = load_config(config_path=config_path)
    Path(config.local_store_dir).mkdir(parents=True, exist_ok=True)
    Path(config.local_store_dir, "reports").mkdir(parents=True, exist_ok=True)
    Path("evals").mkdir(parents=True, exist_ok=True)
    sample_path = Path("evals") / "questions.json"
    if force or not sample_path.exists():
        sample_path.write_text(json.dumps(SAMPLE_QUESTIONS, indent=2), encoding="utf-8")
    legacy_sample_path = Path("evals") / "sample_questions.json"
    if force or not legacy_sample_path.exists():
        legacy_sample_path.write_text(json.dumps(SAMPLE_QUESTIONS, indent=2), encoding="utf-8")
    SQLiteTraceStore(config.storage_path)
    click.echo("Wrote %s" % config_path)
    click.echo("Initialized local trace store: %s" % config.storage_path)
    click.echo("Created sample eval dataset: %s" % sample_path)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    config = _load(ctx)
    store = SQLiteTraceStore(config.storage_path)
    last_eval = store.last_eval_run()
    click.echo("Project: %s" % config.project)
    click.echo("Mode: %s" % config.mode)
    click.echo("Local DB: %s" % config.storage_path)
    click.echo("Trace count: %s" % store.trace_count())
    click.echo("Last eval run: %s" % ((last_eval or {}).get("id") or "None"))
    click.echo("Judge provider: %s" % config.judge_provider)


@cli.group()
def config() -> None:
    """Inspect ContextTrace configuration."""


@config.command("show")
@click.option("--show-secrets", is_flag=True, help="Show API keys instead of masking them.")
@click.pass_context
def config_show(ctx: click.Context, show_secrets: bool) -> None:
    resolved = _load(ctx)
    payload = asdict(resolved)
    if payload.get("api_key") and not show_secrets:
        payload["api_key"] = _mask_secret(str(payload["api_key"]))
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


@cli.group()
def traces() -> None:
    """Inspect local traces."""


@traces.command("list")
@click.option("--limit", default=20, show_default=True, help="Maximum traces to show.")
@click.pass_context
def traces_list(ctx: click.Context, limit: int) -> None:
    client = _client(ctx)
    rows = client.list_traces(limit=limit)
    if not rows:
        click.echo("No traces found.")
        return
    click.echo("trace_id\tquery\tfailure_type\tcitation_support\tcreated_at")
    for trace in rows:
        evaluation = trace.get("evaluation") or {}
        failure = evaluation.get("failure") or {}
        scores = evaluation.get("scores") or {}
        click.echo(
            "%s\t%s\t%s\t%s\t%s"
            % (
                trace.get("id") or trace.get("trace_id"),
                _preview(trace.get("query")),
                failure.get("failure_type") or "not_evaluated",
                scores.get("citation_support", ""),
                trace.get("created_at") or "",
            )
        )


@traces.command("show")
@click.argument("trace_id")
@click.pass_context
def traces_show(ctx: click.Context, trace_id: str) -> None:
    trace = _client(ctx).get_trace(trace_id)
    answer = trace.get("answer") or {}
    evaluation = trace.get("evaluation") or {}
    failure = evaluation.get("failure") or {}
    scores = evaluation.get("scores") or {}
    click.echo("Trace: %s" % trace.get("id"))
    click.echo("Project: %s" % trace.get("project"))
    click.echo("Query: %s" % trace.get("query"))
    click.echo("Answer: %s" % _preview(answer.get("answer"), limit=500))
    click.echo("Failure type: %s" % (failure.get("failure_type") or "not_evaluated"))
    click.echo("Severity: %s" % (failure.get("severity") or "unknown"))
    click.echo("Citation support: %s" % scores.get("citation_support", ""))
    click.echo("Unsupported claim rate: %s" % scores.get("unsupported_claim_rate", ""))
    click.echo("Chunks: %s" % len(trace.get("chunks") or []))
    click.echo("Citation checks: %s" % len(trace.get("citation_checks") or []))


@cli.group("trace")
def trace_alias() -> None:
    """Backward-compatible alias for traces."""


trace_alias.add_command(traces_list, "list")
trace_alias.add_command(traces_show, "show")


@cli.command()
@click.option("--last", is_flag=True, help="Export the most recent trace.")
@click.option("--trace-id", default=None, help="Trace ID to export.")
@click.option("--eval-run", default=None, help="Eval run ID to export.")
@click.option("--output", default=None, help="HTML file to write.")
@click.option("--open", "open_browser", is_flag=True, help="Open the report in the default browser.")
@click.pass_context
def report(
    ctx: click.Context,
    last: bool,
    trace_id: Optional[str],
    eval_run: Optional[str],
    output: Optional[str],
    open_browser: bool,
) -> None:
    config = _load(ctx)
    client = _client(ctx)
    report_dir = Path(config.local_store_dir) / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    if eval_run:
        store = SQLiteTraceStore(config.storage_path)
        run = store.get_eval_run(eval_run)
        traces_for_run = [
            store.get_trace(question["trace_id"])
            for question in run.get("questions") or []
            if question.get("trace_id")
        ]
        output_path = output or str(report_dir / ("%s.html" % eval_run))
        written = ReportGenerator().generate_eval_report(run, traces_for_run, path=output_path)
    else:
        if not trace_id:
            last = True
        selected = client.last_trace() if last else client.get_trace(str(trace_id))
        if selected is None:
            raise click.ClickException("No traces found.")
        output_path = output or str(report_dir / ("%s.html" % selected["id"]))
        written = ReportGenerator().generate(selected, path=output_path)

    click.echo("Wrote %s" % written)
    if open_browser:
        webbrowser.open(Path(written).resolve().as_uri())


@cli.command("verify")
@click.argument("trace_json")
@click.option("--json", "json_output", is_flag=True, help="Print the full verification result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML verification report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic"]), help="Evidence scoring mode.")
@click.option("--fail-on", multiple=True, help="Fail on unsupported, partial_support, citation_mismatch, should_abstain, contradicted, unverifiable, no_citation, or any_failure.")
def verify_command(
    trace_json: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
) -> int:
    """Verify claim-level evidence support for a portable RAG trace JSON file."""

    try:
        trace = load_trace_file(trace_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    result = verify_trace(trace, mode=mode)
    written_report = _write_verify_report(
        result,
        trace,
        report=report,
        out=out,
        default_name="%s_verify.html" % Path(trace_json).stem,
    )
    return _print_verify_result(
        result,
        json_output=json_output,
        written_report=written_report,
        fail_on=fail_on,
    )


@cli.command("verify-demo")
@click.argument("demo_name", required=False, default="unsupported_claim")
@click.option("--json", "json_output", is_flag=True, help="Print the full verification result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML verification report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic"]), help="Evidence scoring mode.")
@click.option("--fail-on", multiple=True, help="Fail on unsupported, partial_support, citation_mismatch, should_abstain, contradicted, unverifiable, no_citation, or any_failure.")
def verify_demo_command(
    demo_name: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
) -> int:
    """Run a bundled claim-level verification demo."""

    try:
        trace = load_verify_demo(demo_name)
    except KeyError as exc:
        raise click.ClickException(
            "Unknown verify demo %s. Available demos: %s"
            % (demo_name, ", ".join(list_verify_demos()))
        ) from exc

    result = verify_trace(trace, mode=mode)
    written_report = _write_verify_report(
        result,
        trace,
        report=report,
        out=out,
        default_name="%s_verify_demo.html" % demo_name,
    )
    return _print_verify_result(
        result,
        json_output=json_output,
        written_report=written_report,
        fail_on=fail_on,
    )


@cli.command("verify-benchmark")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic"]), help="Evidence scoring mode.")
@click.option("--case-set", default="contexttrace", show_default=True, type=click.Choice(["contexttrace", "external", "all"]), help="Benchmark case set to run.")
@click.option("--json", "json_output", is_flag=True, help="Print benchmark results as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML benchmark report.")
@click.option("--out", default=None, help="HTML benchmark report path. Implies --report when provided.")
def verify_benchmark_command(mode: str, case_set: str, json_output: bool, report: bool, out: Optional[str]) -> int:
    """Run the bundled verification precision/recall benchmark."""

    result = run_verify_benchmark(mode=mode, case_set=case_set)
    written_report = None
    if report or out:
        output_path = out or str(Path(".contexttrace") / "reports" / ("verify_benchmark_%s.html" % mode))
        written_report = write_verify_benchmark_report(result, path=output_path)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        return 0

    click.echo("Mode: %s" % result["mode"])
    click.echo("Case source: %s" % result["case_source"])
    click.echo("Cases: %s" % result["cases"])
    click.echo("Exact match rate: %.3f" % float(result["exact_match_rate"]))
    click.echo("Verdict match rate: %.3f" % float(result["verdict_match_rate"]))
    click.echo("Citation match rate: %.3f" % float(result["citation_match_rate"]))
    click.echo("Abstention match rate: %.3f" % float(result["abstention_match_rate"]))
    click.echo("label\tprecision\trecall\tf1\ttp\tfp\tfn")
    for label, metrics in result["per_label"].items():
        click.echo(
            "%s\t%.3f\t%.3f\t%.3f\t%s\t%s\t%s"
            % (
                label,
                float(metrics["precision"]),
                float(metrics["recall"]),
                float(metrics["f1"]),
                metrics["tp"],
                metrics["fp"],
                metrics["fn"],
            )
        )
    missed = [row for row in result["rows"] if not row["exact_match"]]
    if missed:
        click.echo("Mismatches:")
        for row in missed:
            click.echo(
                "- %s expected=%s predicted=%s"
                % (row["id"], ",".join(row["expected"]), ",".join(row["predicted"]))
            )
    if written_report:
        click.echo("Report: %s" % written_report)
    return 0


def _write_verify_report(
    result: dict,
    trace: object,
    *,
    report: bool,
    out: Optional[str],
    default_name: str,
) -> Optional[str]:
    if not report and not out:
        return None
    output_path = out or str(Path(".contexttrace") / "reports" / default_name)
    return VerifyReportGenerator().generate(result, trace, path=output_path)


def _print_verify_result(
    result: dict,
    *,
    json_output: bool,
    written_report: Optional[str],
    fail_on: tuple[str, ...] = (),
) -> int:
    fail_messages = _verify_failures(result, fail_on)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        for message in fail_messages:
            click.echo("Verification failed: %s" % message, err=True)
        return 1 if fail_messages else 0
    summary = result["summary"]
    click.echo("Claims verified: %s" % summary["total_claims"])
    click.echo(
        "Supported: {supported} | Partial: {partially_supported} | Unsupported: {unsupported} | Unverifiable: {unverifiable} | Contradicted: {contradicted}".format(
            **summary
        )
    )
    click.echo("Support rate: %.3f" % float(summary["support_rate"]))
    click.echo("Unsupported claim rate: %.3f" % float(summary["unsupported_claim_rate"]))
    click.echo("Citation mismatches: %s" % summary["citation_mismatches"])
    click.echo("Failure type: %s" % summary["failure_type"])
    click.echo("Primary root cause: %s" % summary.get("primary_root_cause", "unknown"))
    click.echo("Should abstain: %s" % str(summary["should_abstain"]).lower())
    click.echo("Suggested fix: %s" % summary["suggested_fix"])
    if written_report:
        click.echo("Report: %s" % written_report)
    for message in fail_messages:
        click.echo("Verification failed: %s" % message, err=True)
    return 1 if fail_messages else 0


def _verify_failures(result: dict, fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    claims = result.get("claims") or []
    failure_types = set(summary.get("failure_types") or [])
    messages = []
    for raw_rule in fail_on:
        rule = raw_rule.strip().lower().replace("-", "_")
        if rule == "unsupported" and int(summary.get("unsupported") or 0) > 0:
            messages.append("unsupported claim detected")
        elif rule in {"partial", "partial_support", "partially_supported"} and int(summary.get("partially_supported") or 0) > 0:
            messages.append("partially supported claim detected")
        elif rule == "citation_mismatch" and "citation_mismatch" in failure_types:
            messages.append("citation mismatch detected")
        elif rule == "should_abstain" and bool(summary.get("should_abstain")):
            messages.append("answer should have abstained")
        elif rule == "contradicted" and int(summary.get("contradicted") or 0) > 0:
            messages.append("contradicted claim detected")
        elif rule == "unverifiable" and int(summary.get("unverifiable") or 0) > 0:
            messages.append("unverifiable claim detected")
        elif rule == "no_citation" and any(claim.get("citation_status") == "claim_has_no_citation" for claim in claims):
            messages.append("claim without citation detected")
        elif rule == "any_failure" and failure_types != {"no_failure_detected"}:
            messages.append("verification failure detected")
        elif rule not in {
            "unsupported",
            "partial",
            "partial_support",
            "partially_supported",
            "citation_mismatch",
            "should_abstain",
            "contradicted",
            "unverifiable",
            "no_citation",
            "any_failure",
        }:
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


@cli.command("eval")
@click.option("--dataset", required=True, help="Path to eval questions JSON.")
@click.option("--endpoint", default=None, help="RAG endpoint URL. Defaults to config eval_endpoint.")
@click.option("--method", default="POST", type=click.Choice(["GET", "POST"], case_sensitive=False), help="Endpoint method.")
@click.option("--input-key", default="question", show_default=True, help="Request body/query key for the question.")
@click.option("--answer-path", default="$.answer", show_default=True, help="JSONPath for answer extraction.")
@click.option("--contexts-path", default="$.contexts", show_default=True, help="JSONPath for context extraction.")
@click.option("--citations-path", default="$.citations", show_default=True, help="JSONPath for citation extraction.")
@click.option("--body-template", default=None, help="JSON body template. Use {{query}} where the question should be inserted.")
@click.option("--endpoint-header", multiple=True, help="Header formatted as Name:Value. May be repeated.")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Per-request timeout.")
@click.option("--report-path", default=None, help="HTML report path. Defaults to .contexttrace/reports/eval_<id>.html.")
@click.option("--api-key", default=None, help="Accepted for compatibility; local mode does not require it.")
@click.option("--contexttrace-url", default=None, help="Accepted for compatibility; local mode stores traces locally.")
@click.option("--min-citation-support", default=0.0, show_default=True, type=float, help="Fail when average citation support is below this value.")
@click.option("--max-unsupported-claim-rate", default=1.0, show_default=True, type=float, help="Fail when unsupported claim rate is above this value.")
@click.option("--max-failure-rate", default=1.0, show_default=True, type=float, help="Fail when failure rate is above this value.")
@click.option("--summary-path", default=None, help="Optional markdown summary output path.")
@click.option("--fail-on", multiple=True, help="Threshold rule such as failure_rate>0.25. May be repeated.")
@click.option("--results-path", default=None, help="Optional JSON results output path.")
@click.pass_context
def eval_command(
    ctx: click.Context,
    dataset: str,
    endpoint: Optional[str],
    method: str,
    input_key: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    body_template: Optional[str],
    endpoint_header: tuple[str, ...],
    timeout: float,
    report_path: Optional[str],
    api_key: Optional[str],
    contexttrace_url: Optional[str],
    min_citation_support: float,
    max_unsupported_claim_rate: float,
    max_failure_rate: float,
    summary_path: Optional[str],
    fail_on: tuple[str, ...],
    results_path: Optional[str],
) -> None:
    config = _load(ctx)
    resolved_endpoint = endpoint or config.eval_endpoint
    if not resolved_endpoint:
        raise click.ClickException("--endpoint or eval_endpoint in contexttrace.yaml is required.")
    body = json.loads(body_template) if body_template else None
    result = run_endpoint_eval(
        dataset_path=dataset,
        endpoint=resolved_endpoint,
        contexttrace=_client(ctx),
        method=method,
        headers=_parse_headers(list(endpoint_header)),
        body_template=body,
        input_key=input_key,
        answer_path=answer_path,
        contexts_path=contexts_path,
        citations_path=citations_path,
        timeout=timeout,
        report_path=report_path,
    )
    click.echo("Questions tested: %s" % result.questions_tested)
    click.echo("Reliability score: %s" % result.reliability_score)
    click.echo("Failure rate: %s" % result.failure_rate)
    click.echo("Avg citation support: %s" % result.avg_citation_support)
    click.echo("Unsupported claim rate: %s" % result.unsupported_claim_rate)
    click.echo("Top failures: %s" % (", ".join(result.top_failures) or "None"))
    if result.report_path:
        click.echo("Report: %s" % result.report_path)
    if summary_path:
        Path(summary_path).write_text(_eval_markdown(result), encoding="utf-8")
        click.echo("Summary: %s" % summary_path)
    if results_path:
        Path(results_path).parent.mkdir(parents=True, exist_ok=True)
        Path(results_path).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        click.echo("Results: %s" % results_path)
    metrics = {
        "failure_rate": result.failure_rate,
        "citation_support": result.avg_citation_support,
        "avg_citation_support": result.avg_citation_support,
        "unsupported_claim_rate": result.unsupported_claim_rate,
        "reliability_score": result.reliability_score,
    }
    parsed_fail_on = parse_thresholds(fail_on)
    fail_on_messages = threshold_failures(metrics, parsed_fail_on)
    for message in fail_on_messages:
        click.echo("Threshold failed: %s" % message, err=True)
    failed = (
        result.avg_citation_support < min_citation_support
        or result.unsupported_claim_rate > max_unsupported_claim_rate
        or result.failure_rate > max_failure_rate
        or bool(fail_on_messages)
    )
    if failed:
        return 1
    return 0


@cli.command()
@click.option("--dataset", default="refund_policy", show_default=True, help="Demo dataset name or path.")
@click.option("--strategy", default="adaptive", show_default=True, help="Demo retrieval strategy.")
@click.pass_context
def demo(ctx: click.Context, dataset: str, strategy: str) -> None:
    client = _client(ctx)
    config = _load(ctx)
    report_path = Path(config.local_store_dir) / "reports" / ("%s_demo.html" % Path(dataset).name)
    result = run_demo_dataset(
        dataset=dataset,
        contexttrace=client,
        strategy=strategy,
        report_path=str(report_path),
    )
    click.echo("Dataset: %s" % result.dataset)
    click.echo("Traces created: %s" % len(result.trace_ids))
    click.echo("Reliability score: %s" % result.summary.get("reliability_score"))
    click.echo("Failure rate: %s" % result.summary.get("failure_rate"))
    click.echo("Citation support: %s" % result.summary.get("citation_support"))
    click.echo("Top failures: %s" % (", ".join(result.summary.get("top_failures") or []) or "None"))
    click.echo("Report: %s" % result.report_path)


@cli.command()
@click.option("--dataset", required=True, help="Demo dataset name or path.")
@click.option("--strategy", "strategies", multiple=True, help="Strategy to run. May be repeated.")
@click.option("--output-dir", default=".contexttrace/benchmarks", show_default=True, help="Benchmark output directory.")
@click.option("--fail-on", multiple=True, help="Threshold rule such as failure_rate>0.25. May be repeated.")
@click.option("--report-path", default=None, help="Optional benchmark HTML report path.")
@click.pass_context
def benchmark(
    ctx: click.Context,
    dataset: str,
    strategies: tuple[str, ...],
    output_dir: str,
    fail_on: tuple[str, ...],
    report_path: Optional[str],
) -> None:
    result = run_local_benchmark(
        dataset=dataset,
        contexttrace=_client(ctx),
        output_dir=output_dir,
        strategies=strategies or BENCHMARK_STRATEGIES,
        fail_on=fail_on,
        report_path=report_path,
    )
    summary = result["summary"]
    click.echo("Status: %s" % result["status"])
    click.echo("Questions tested: %s" % summary.get("questions_tested"))
    click.echo("Reliability score: %s" % summary.get("reliability_score"))
    click.echo("Failure rate: %s" % summary.get("failure_rate"))
    click.echo("Citation support: %s" % summary.get("citation_support"))
    click.echo("Unsupported claim rate: %s" % summary.get("unsupported_claim_rate"))
    click.echo("Results: %s" % result["results_path"])
    click.echo("Summary: %s" % result["summary_path"])
    click.echo("Report: %s" % result["report_path"])
    for failure in result["threshold_failures"]:
        click.echo("Threshold failed: %s" % failure, err=True)
    if result["threshold_failures"]:
        return 1
    return 0


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    config_path = Path(ctx.obj.get("config_path") or "contexttrace.yaml")
    config = _load(ctx)
    checks = []
    checks.append(("config exists", config_path.exists()))
    try:
        SQLiteTraceStore(config.storage_path)
        checks.append(("SQLite writable", True))
    except Exception:
        checks.append(("SQLite writable", False))
    checks.append(("demo datasets available", bool(list_demo_datasets())))
    if config.judge_provider in {"openai", "openai-compatible"}:
        checks.append(("LLM API key present", bool(config.api_key)))
    else:
        checks.append(("LLM API key present", True))
    if config.eval_endpoint:
        checks.append(("endpoint reachable", _endpoint_reachable(config.eval_endpoint)))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        click.echo("%s: %s" % ("OK" if ok else "FAIL", name))
    if failed:
        raise click.ClickException("Doctor found %s failed check(s)." % len(failed))


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.pass_context
def viewer(ctx: click.Context, host: str, port: int) -> None:
    config = _load(ctx)
    serve_viewer(storage_path=config.storage_path, host=host, port=port)


def main(argv: Optional[list[str]] = None) -> int:
    try:
        result = cli.main(args=argv, prog_name="contexttrace", standalone_mode=False)
        return int(result or 0)
    except click.exceptions.Exit as exc:
        return int(exc.exit_code or 0)
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return int(exc.exit_code)
    except ContextTraceError as exc:
        click.echo("ContextTrace failed: %s" % exc, err=True)
        return 2
    except ValueError as exc:
        click.echo("ContextTrace failed: %s" % exc, err=True)
        return 2


def _load(ctx: click.Context) -> ContextTraceConfig:
    return load_config(config_path=(ctx.obj or {}).get("config_path"))


def _client(ctx: click.Context) -> ContextTrace:
    config_path = (ctx.obj or {}).get("config_path")
    return ContextTrace(config_path=config_path)


def _parse_headers(values: list[str]) -> dict[str, str]:
    headers = {}
    for value in values:
        if ":" not in value:
            raise click.ClickException("Endpoint headers must be formatted as Name:Value.")
        name, header_value = value.split(":", 1)
        headers[name.strip()] = header_value.strip()
    return headers


def _mask_secret(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return "%s***%s" % (value[:3], value[-3:])


def _preview(value: object, *, limit: int = 100) -> str:
    text = "" if value is None else str(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _endpoint_reachable(endpoint: str) -> bool:
    request = urllib.request.Request(endpoint, method="GET")
    try:
        urllib.request.urlopen(request, timeout=2).close()
        return True
    except urllib.error.HTTPError:
        return True
    except urllib.error.URLError:
        return False


def _eval_markdown(result: object) -> str:
    return "\n".join(
        [
            "# ContextTrace Local Eval Summary",
            "",
            "- Questions tested: %s" % getattr(result, "questions_tested", 0),
            "- Reliability score: %s" % getattr(result, "reliability_score", 0),
            "- Failure rate: %s" % getattr(result, "failure_rate", 0),
            "- Average citation support: %s" % getattr(result, "avg_citation_support", 0),
            "- Unsupported claim rate: %s" % getattr(result, "unsupported_claim_rate", 0),
            "- Top failures: %s" % (", ".join(getattr(result, "top_failures", []) or []) or "None"),
            "- Report: %s" % (getattr(result, "report_path", None) or "Not generated"),
            "",
        ]
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
