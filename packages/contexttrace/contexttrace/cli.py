from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import click

from contexttrace._version import __version__
from contexttrace.capture import write_rag_trace
from contexttrace.capture_endpoint import capture_endpoint_trace, capture_response_trace
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
    audit_failures,
    audit_trace,
    build_judge_provider,
    run_judge_calibration,
    compare_failures,
    compare_trace_files,
    list_verify_demos,
    load_trace_file,
    load_verify_demo,
    verify_trace,
    write_judge_calibration_report,
)
from contexttrace.verify.benchmark import run_verify_benchmark, write_verify_benchmark_report
from contexttrace.verify.audit_benchmark import run_audit_benchmark, write_audit_benchmark_report
from contexttrace.verify.audit_report import AuditReportGenerator
from contexttrace.verify.compare_report import CompareReportGenerator
from contexttrace.verify.qa import qa_failures, qa_trace
from contexttrace.verify.qa_report import QAReportGenerator
from contexttrace.verify.report import VerifyReportGenerator
from contexttrace.verify.suite import (
    add_trace_files_to_suite,
    create_suite_from_trace_files,
    list_suite_cases,
    load_suite_file,
    load_suite_result_file,
    prune_suite_cases,
    remove_suite_cases,
    run_suite,
    suite_failures,
    write_suite_file,
    write_suite_result,
)
from contexttrace.verify.suite_report import SuiteReportGenerator
from contexttrace.verify.trace_inspect import inspect_trace
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
    if payload.get("judge_api_key") and not show_secrets:
        payload["judge_api_key"] = _mask_secret(str(payload["judge_api_key"]))
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
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml", "judge"]), help="Evidence scoring mode.")
@click.option("--judge-provider", default=None, help="Judge provider for --mode judge, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers; prefer CONTEXTTRACE_JUDGE_API_KEY in CI.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.option("--fail-on", multiple=True, help="Fail on unsupported, partial_support, citation_mismatch, should_abstain, contradicted, unverifiable, no_citation, or any_failure.")
@click.pass_context
def verify_command(
    ctx: click.Context,
    trace_json: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
    fail_on: tuple[str, ...],
) -> int:
    """Verify claim-level evidence support for a portable RAG trace JSON file."""

    try:
        trace = load_trace_file(trace_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    result = verify_trace(
        trace,
        mode=mode,
        judge=_judge_from_cli(
            ctx,
            mode=mode,
            provider=judge_provider,
            base_url=judge_base_url,
            api_key=judge_api_key,
            model=judge_model,
        ),
    )
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


@cli.command("inspect")
@click.argument("trace_json")
@click.option("--json", "json_output", is_flag=True, help="Print trace inspection as JSON.")
def inspect_command(trace_json: str, json_output: bool) -> int:
    """Inspect portable RAG trace shape before verification."""

    try:
        trace = load_trace_file(trace_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    result = inspect_trace(trace, trace_path=trace_json)
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return 0

    click.echo("Trace: %s" % trace_json)
    click.echo("Query: %s" % result["query"])
    click.echo("Answer preview: %s" % result["answer_preview"])
    click.echo("Claims extracted: %s" % len(result["claims"]))
    for claim in result["claims"]:
        click.echo("- %s: %s" % (claim["id"], claim["text"]))

    contexts = result["contexts"]
    click.echo("Contexts: %s (%s unique IDs)" % (contexts["count"], contexts["unique_ids"]))
    if contexts["duplicate_ids"]:
        click.echo("Duplicate context IDs: %s" % ", ".join(contexts["duplicate_ids"]))
    if contexts["empty_text_ids"]:
        click.echo("Empty context text IDs: %s" % ", ".join(contexts["empty_text_ids"]))

    citations = result["citations"]
    click.echo("Citations: %s" % citations["count"])
    if citations["missing_source_ids"]:
        click.echo("Missing citation source IDs: %s" % ", ".join(citations["missing_source_ids"]))

    if result["metadata_keys"]:
        click.echo("Metadata keys: %s" % ", ".join(result["metadata_keys"]))

    warnings = result["warnings"]
    if warnings:
        click.echo("Warnings:")
        for warning in warnings:
            click.echo("- %s" % warning)

    click.echo("Suggested next commands:")
    for command in result["suggested_next_commands"]:
        click.echo("- %s" % command)
    return 0


@cli.command("qa")
@click.argument("trace_json")
@click.option("--corpus", "corpus_path", default=None, help="Optional local corpus directory or file for retrieval/corpus audit.")
@click.option("--json", "json_output", is_flag=True, help="Print the full QA result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML evidence QA report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode.")
@click.option("--fail-on", multiple=True, help="Fail on high_risk, medium_risk, any_risk, unsupported, should_abstain, audit_failure, or inspect_warning.")
def qa_command(
    trace_json: str,
    corpus_path: Optional[str],
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
) -> int:
    """Run inspect, verify, optional audit, and risk summary for a RAG trace."""

    try:
        trace = load_trace_file(trace_json)
        result = qa_trace(trace, trace_path=trace_json, corpus_path=corpus_path, mode=mode)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    written_report = None
    if report or out:
        default_name = "%s_qa.html" % Path(trace_json).stem
        output_path = out or str(Path(".contexttrace") / "reports" / default_name)
        written_report = QAReportGenerator().generate(result, trace, path=output_path)

    fail_messages = qa_failures(result, fail_on)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        for message in fail_messages:
            click.echo("QA failed: %s" % message, err=True)
        return 1 if fail_messages else 0

    summary = result["summary"]
    click.echo("Risk level: %s" % summary["risk_level"])
    click.echo("Risk score: %s" % summary["risk_score"])
    click.echo("Primary issue: %s" % summary["primary_issue"])
    click.echo("Claims: %s" % summary["total_claims"])
    click.echo("Support rate: %.3f" % float(summary.get("support_rate") or 0.0))
    click.echo("Unsupported claim rate: %.3f" % float(summary.get("unsupported_claim_rate") or 0.0))
    click.echo("Should abstain: %s" % str(summary.get("should_abstain")).lower())
    click.echo("Inspection warnings: %s" % summary["inspect_warnings"])
    if summary.get("corpus_audited"):
        click.echo("Audit label: %s" % summary.get("audit_primary_label"))
        stages = summary.get("failure_stages") or {}
        if stages:
            click.echo(
                "Failure stages: %s"
                % ", ".join("%s=%s" % (stage, count) for stage, count in sorted(stages.items()))
            )
    else:
        click.echo("Audit label: not_run")

    actions = list(result.get("next_actions") or [])
    if actions:
        click.echo("Next actions:")
        for action in actions:
            click.echo("- %s" % action)
    if written_report:
        click.echo("Report: %s" % written_report)
    for message in fail_messages:
        click.echo("QA failed: %s" % message, err=True)
    return 1 if fail_messages else 0


@cli.group("suite")
def suite_group() -> None:
    """Create and run local RAG regression suites."""


@suite_group.command("create")
@click.argument("trace_json", nargs=-1, required=True)
@click.option("--out", default="contexttrace-suite.json", show_default=True, help="Suite JSON file to write.")
@click.option("--name", default=None, help="Suite name.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode for baseline QA.")
@click.option("--corpus", "corpus_path", default=None, help="Optional local corpus directory or file for baseline retrieval/corpus audit.")
def suite_create_command(
    trace_json: tuple[str, ...],
    out: str,
    name: Optional[str],
    mode: str,
    corpus_path: Optional[str],
) -> int:
    """Create a suite from saved portable RAG trace files."""

    try:
        suite = create_suite_from_trace_files(
            trace_json,
            name=name,
            mode=mode,
            corpus_path=corpus_path,
        )
        written = write_suite_file(suite, out)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Suite: %s" % written)
    click.echo("Cases: %s" % len(suite.get("cases") or []))
    click.echo("Policy: saved cases must pass on replay")
    return 0


@suite_group.command("add")
@click.argument("suite_json")
@click.argument("trace_json", nargs=-1, required=True)
@click.option("--out", default=None, help="Suite JSON file to write. Defaults to overwriting suite_json.")
@click.option("--mode", default=None, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode for added baselines. Defaults to the suite mode.")
@click.option("--corpus", "corpus_path", default=None, help="Optional local corpus directory or file for baseline retrieval/corpus audit.")
@click.option("--replace", is_flag=True, help="Replace existing cases with the same generated case IDs.")
def suite_add_command(
    suite_json: str,
    trace_json: tuple[str, ...],
    out: Optional[str],
    mode: Optional[str],
    corpus_path: Optional[str],
    replace: bool,
) -> int:
    """Add saved portable RAG traces to an existing suite."""

    try:
        suite = load_suite_file(suite_json)
        result = add_trace_files_to_suite(
            suite,
            trace_json,
            mode=mode,
            corpus_path=corpus_path,
            replace=replace,
        )
        written = write_suite_file(result["suite"], out or suite_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Suite: %s" % written)
    click.echo("Added: %s" % len(result["added_case_ids"]))
    if result["added_case_ids"]:
        click.echo("Added case IDs: %s" % ", ".join(result["added_case_ids"]))
    click.echo("Replaced: %s" % result["replaced"])
    click.echo("Cases: %s" % len(result["suite"].get("cases") or []))
    return 0


@suite_group.command("list")
@click.argument("suite_json")
@click.option("--json", "json_output", is_flag=True, help="Print cases as JSON.")
def suite_list_command(suite_json: str, json_output: bool) -> int:
    """List cases in a local regression suite."""

    try:
        suite = load_suite_file(suite_json)
        rows = list_suite_cases(suite)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        click.echo(json.dumps({"suite": suite.get("name"), "cases": rows}, indent=2))
        return 0

    click.echo("Suite: %s" % (suite.get("name") or suite_json))
    click.echo("Cases: %s" % len(rows))
    click.echo("id\tbaseline_risk\tbaseline_issue\tsupport_rate\tquery")
    for row in rows:
        click.echo(
            "%s\t%s\t%s\t%s\t%s"
            % (
                row.get("id"),
                row.get("baseline_risk_level") or "",
                row.get("baseline_primary_issue") or "",
                row.get("baseline_support_rate") if row.get("baseline_support_rate") is not None else "",
                _preview(row.get("query"), limit=90),
            )
        )
    return 0


@suite_group.command("remove")
@click.argument("suite_json")
@click.argument("case_id", nargs=-1, required=True)
@click.option("--out", default=None, help="Suite JSON file to write. Defaults to overwriting suite_json.")
def suite_remove_command(suite_json: str, case_id: tuple[str, ...], out: Optional[str]) -> int:
    """Remove one or more case IDs from a suite."""

    try:
        suite = load_suite_file(suite_json)
        result = remove_suite_cases(suite, case_id)
        written = write_suite_file(result["suite"], out or suite_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Suite: %s" % written)
    click.echo("Removed: %s" % len(result["removed_case_ids"]))
    if result["removed_case_ids"]:
        click.echo("Removed case IDs: %s" % ", ".join(result["removed_case_ids"]))
    if result["missing_case_ids"]:
        click.echo("Missing case IDs: %s" % ", ".join(result["missing_case_ids"]))
    click.echo("Cases: %s" % len(result["suite"].get("cases") or []))
    return 1 if result["missing_case_ids"] else 0


@suite_group.command("prune")
@click.argument("suite_json")
@click.option("--results", "results_json", required=True, help="Suite result JSON from `contexttrace suite run`.")
@click.option("--status", "statuses", multiple=True, default=("passed",), show_default=True, help="Result status to remove. May be repeated.")
@click.option("--out", default=None, help="Suite JSON file to write. Defaults to overwriting suite_json.")
def suite_prune_command(
    suite_json: str,
    results_json: str,
    statuses: tuple[str, ...],
    out: Optional[str],
) -> int:
    """Remove cases by status from a saved suite result."""

    try:
        suite = load_suite_file(suite_json)
        result_payload = load_suite_result_file(results_json)
        result = prune_suite_cases(suite, result_payload, statuses=statuses)
        written = write_suite_file(result["suite"], out or suite_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Suite: %s" % written)
    click.echo("Pruned statuses: %s" % ", ".join(result["statuses"]))
    click.echo("Removed: %s" % len(result["removed_case_ids"]))
    if result["removed_case_ids"]:
        click.echo("Removed case IDs: %s" % ", ".join(result["removed_case_ids"]))
    click.echo("Cases: %s" % len(result["suite"].get("cases") or []))
    return 0


@suite_group.command("run")
@click.argument("suite_json")
@click.option("--endpoint", default=None, help="RAG endpoint URL. Defaults to config eval_endpoint.")
@click.option("--method", default="POST", type=click.Choice(["GET", "POST"], case_sensitive=False), help="Endpoint method.")
@click.option("--input-key", default="question", show_default=True, help="Request body/query key for the question.")
@click.option("--answer-path", default="$.answer", show_default=True, help="JSONPath for answer extraction.")
@click.option("--contexts-path", default="$.contexts", show_default=True, help="JSONPath for context extraction.")
@click.option("--citations-path", default="$.citations", show_default=True, help="JSONPath for citation extraction.")
@click.option("--metadata-path", default="$.metadata", show_default=True, help="JSONPath for response metadata extraction.")
@click.option("--body-template", default=None, help="JSON body template. Use {{query}} where the question should be inserted.")
@click.option("--endpoint-header", multiple=True, help="Header formatted as Name:Value. May be repeated.")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Per-request timeout.")
@click.option("--corpus", "corpus_path", default=None, help="Optional local corpus directory or file for retrieval/corpus audit.")
@click.option("--out", default=None, help="Suite result JSON path.")
@click.option("--json", "json_output", is_flag=True, help="Print the full suite result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML suite report.")
@click.option("--report-out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default=None, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode. Defaults to the suite mode.")
@click.option("--fail-on", multiple=True, help="Fail on failed_case, regression, unsupported, should_abstain, high_risk, medium_risk, error, or any_failure.")
@click.pass_context
def suite_run_command(
    ctx: click.Context,
    suite_json: str,
    endpoint: Optional[str],
    method: str,
    input_key: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    metadata_path: str,
    body_template: Optional[str],
    endpoint_header: tuple[str, ...],
    timeout: float,
    corpus_path: Optional[str],
    out: Optional[str],
    json_output: bool,
    report: bool,
    report_out: Optional[str],
    mode: Optional[str],
    fail_on: tuple[str, ...],
) -> int:
    """Replay a regression suite against a running RAG endpoint."""

    config = _load(ctx)
    resolved_endpoint = endpoint or config.eval_endpoint
    if not resolved_endpoint:
        raise click.ClickException("--endpoint or eval_endpoint in contexttrace.yaml is required.")

    try:
        suite = load_suite_file(suite_json)
        body = json.loads(body_template) if body_template else None
        result = run_suite(
            suite,
            endpoint=resolved_endpoint,
            method=method,
            headers=_parse_headers(list(endpoint_header)),
            body_template=body,
            input_key=input_key,
            answer_path=answer_path,
            contexts_path=contexts_path,
            citations_path=citations_path,
            metadata_path=metadata_path,
            timeout=timeout,
            corpus_path=corpus_path,
            mode=mode,
        )
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            "Invalid --body-template JSON at line %s column %s: %s"
            % (exc.lineno, exc.colno, exc.msg)
        ) from exc
    except (RuntimeError, ValueError, VerificationInputError) as exc:
        raise click.ClickException(str(exc)) from exc

    output_path = out or str(
        Path(".contexttrace")
        / "suites"
        / ("%s_results.json" % _safe_filename(str(result.get("suite_name") or Path(suite_json).stem)))
    )
    written_result = write_suite_result(result, output_path)

    written_report = None
    if report or report_out:
        report_path = report_out or str(
            Path(".contexttrace")
            / "reports"
            / ("%s_suite.html" % _safe_filename(str(result.get("suite_name") or Path(suite_json).stem)))
        )
        written_report = SuiteReportGenerator().generate(result, path=report_path)

    effective_fail_on = fail_on or ("failed_case", "error")
    fail_messages = suite_failures(result, effective_fail_on)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo("Results: %s" % written_result, err=True)
        click.echo(json.dumps(result, indent=2))
        for message in fail_messages:
            click.echo("Suite failed: %s" % message, err=True)
        return 1 if fail_messages else 0

    _print_suite_result(result, written_result=written_result, written_report=written_report)
    for message in fail_messages:
        click.echo("Suite failed: %s" % message, err=True)
    return 1 if fail_messages else 0


@suite_group.command("report")
@click.argument("results_json")
@click.option("--out", default=None, help="HTML report path.")
def suite_report_command(results_json: str, out: Optional[str]) -> int:
    """Generate a local HTML report from a suite result JSON file."""

    try:
        result = load_suite_result_file(results_json)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc
    output_path = out or str(Path(".contexttrace") / "reports" / ("%s.html" % Path(results_json).stem))
    written = SuiteReportGenerator().generate(result, path=output_path)
    click.echo("Report: %s" % written)
    return 0


@cli.command("verify-demo")
@click.argument("demo_name", required=False, default="unsupported_claim")
@click.option("--json", "json_output", is_flag=True, help="Print the full verification result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML verification report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml", "judge"]), help="Evidence scoring mode.")
@click.option("--judge-provider", default=None, help="Judge provider for --mode judge, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers; prefer CONTEXTTRACE_JUDGE_API_KEY in CI.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.option("--fail-on", multiple=True, help="Fail on unsupported, partial_support, citation_mismatch, should_abstain, contradicted, unverifiable, no_citation, or any_failure.")
@click.pass_context
def verify_demo_command(
    ctx: click.Context,
    demo_name: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
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

    result = verify_trace(
        trace,
        mode=mode,
        judge=_judge_from_cli(
            ctx,
            mode=mode,
            provider=judge_provider,
            base_url=judge_base_url,
            api_key=judge_api_key,
            model=judge_model,
        ),
    )
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
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml", "judge"]), help="Evidence scoring mode.")
@click.option("--case-set", default="contexttrace", show_default=True, type=click.Choice(["contexttrace", "external", "all"]), help="Benchmark case set to run.")
@click.option("--json", "json_output", is_flag=True, help="Print benchmark results as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML benchmark report.")
@click.option("--out", default=None, help="HTML benchmark report path. Implies --report when provided.")
@click.option("--judge-provider", default=None, help="Judge provider for --mode judge, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers; prefer CONTEXTTRACE_JUDGE_API_KEY in CI.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.pass_context
def verify_benchmark_command(
    ctx: click.Context,
    mode: str,
    case_set: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
) -> int:
    """Run the bundled verification precision/recall benchmark."""

    result = run_verify_benchmark(
        mode=mode,
        case_set=case_set,
        judge=_judge_from_cli(
            ctx,
            mode=mode,
            provider=judge_provider,
            base_url=judge_base_url,
            api_key=judge_api_key,
            model=judge_model,
        ),
    )
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


@cli.command("judge-calibrate")
@click.option("--case-set", default="all", show_default=True, type=click.Choice(["contexttrace", "external", "all"]), help="Golden benchmark case set to run.")
@click.option("--json", "json_output", is_flag=True, help="Print calibration result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML calibration report.")
@click.option("--out", default=None, help="HTML calibration report path. Implies --report when provided.")
@click.option("--judge-provider", default=None, help="Judge provider, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.option("--min-exact-match-rate", default=0.85, show_default=True, type=float, help="Minimum acceptable failure-label exact match rate.")
@click.option("--min-contradiction-recall", default=0.8, show_default=True, type=float, help="Minimum acceptable contradiction recall.")
@click.option("--max-dangerous-miss-rate", default=0.05, show_default=True, type=float, help="Maximum allowed rate of risky cases predicted as no failure.")
@click.pass_context
def judge_calibrate_command(
    ctx: click.Context,
    case_set: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
    min_exact_match_rate: float,
    min_contradiction_recall: float,
    max_dangerous_miss_rate: float,
) -> int:
    """Calibrate a local judge against golden RAG failure cases."""

    judge = _judge_from_cli(
        ctx,
        mode="judge",
        provider=judge_provider,
        base_url=judge_base_url,
        api_key=judge_api_key,
        model=judge_model,
    )
    result = run_judge_calibration(
        judge=judge,
        case_set=case_set,
        min_exact_match_rate=min_exact_match_rate,
        min_contradiction_recall=min_contradiction_recall,
        max_dangerous_miss_rate=max_dangerous_miss_rate,
    )
    written_report = None
    if report or out:
        judge_name = _safe_filename("%s_%s" % (
            (result.get("judge") or {}).get("provider") or "judge",
            (result.get("judge") or {}).get("model") or "model",
        ))
        output_path = out or str(Path(".contexttrace") / "reports" / ("judge_calibration_%s.html" % judge_name))
        written_report = write_judge_calibration_report(result, path=output_path)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        for failure in result.get("failures") or []:
            click.echo("Calibration failed: %s" % failure, err=True)
        return 1 if result.get("failures") else 0

    scorecard = result["scorecard"]
    click.echo("Status: %s" % result["status"])
    click.echo("Judge: %s" % json.dumps(result.get("judge") or {}, sort_keys=True))
    click.echo("Cases: %s" % result["cases"])
    click.echo("Exact match rate: %.3f" % float(scorecard["exact_match_rate"]))
    click.echo("Verdict match rate: %.3f" % float(scorecard["verdict_match_rate"]))
    click.echo("Citation match rate: %.3f" % float(scorecard["citation_match_rate"]))
    click.echo("Abstention match rate: %.3f" % float(scorecard["abstention_match_rate"]))
    click.echo("Contradiction recall: %.3f" % float(scorecard["contradiction_recall"]))
    click.echo("Dangerous miss rate: %.3f" % float(scorecard["dangerous_miss_rate"]))
    if written_report:
        click.echo("Report: %s" % written_report)
    for failure in result.get("failures") or []:
        click.echo("Calibration failed: %s" % failure, err=True)
    return 1 if result.get("failures") else 0


@cli.command("audit-benchmark")
@click.option("--mode", default="semantic", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode.")
@click.option("--case-set", default="real", show_default=True, type=click.Choice(["real"]), help="Benchmark case set to run.")
@click.option("--json", "json_output", is_flag=True, help="Print audit benchmark results as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML audit benchmark report.")
@click.option("--out", default=None, help="HTML audit benchmark report path. Implies --report when provided.")
def audit_benchmark_command(mode: str, case_set: str, json_output: bool, report: bool, out: Optional[str]) -> int:
    """Run the bundled public-source retrieval audit benchmark."""

    try:
        result = run_audit_benchmark(mode=mode, case_set=case_set)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    written_report = None
    if report or out:
        output_path = out or str(Path(".contexttrace") / "reports" / ("audit_benchmark_%s.html" % mode))
        written_report = write_audit_benchmark_report(result, path=output_path)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        return 0

    click.echo("Mode: %s" % result["mode"])
    click.echo("Case source: %s" % result["case_source"])
    click.echo("Cases: %s" % result["cases"])
    click.echo("Exact match rate: %.3f" % float(result["exact_match_rate"]))
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
                % (row["id"], row["expected"], row["predicted"])
            )
    if written_report:
        click.echo("Report: %s" % written_report)
    return 0


@cli.command("compare")
@click.argument("baseline_json")
@click.argument("current_json")
@click.option("--json", "json_output", is_flag=True, help="Print the full comparison result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML regression report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode for raw trace inputs.")
@click.option("--fail-on", multiple=True, help="Fail on new_failure, new_unsupported, new_citation_mismatch, should_abstain_flip, support_rate_drop, new_root_cause, or any_regression.")
def compare_command(
    baseline_json: str,
    current_json: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
) -> int:
    """Compare two portable RAG traces or verification JSON outputs."""

    try:
        result = compare_trace_files(baseline_json, current_json, mode=mode)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    written_report = None
    if report or out:
        default_name = "%s_vs_%s_compare.html" % (Path(baseline_json).stem, Path(current_json).stem)
        output_path = out or str(Path(".contexttrace") / "reports" / default_name)
        written_report = CompareReportGenerator().generate(result, path=output_path)

    fail_messages = compare_failures(result, fail_on)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        for message in fail_messages:
            click.echo("Comparison failed: %s" % message, err=True)
        return 1 if fail_messages else 0

    summary = result["summary"]
    click.echo("Regression: %s" % str(summary["regression"]).lower())
    click.echo("Support rate: %.3f -> %.3f (%+.3f)" % (
        float(summary.get("support_rate_before") or 0.0),
        float(summary.get("support_rate_after") or 0.0),
        float(summary.get("support_rate_delta") or 0.0),
    ))
    click.echo("Unsupported claim rate delta: %+.3f" % float(summary.get("unsupported_claim_rate_delta") or 0.0))
    click.echo("Citation mismatch delta: %+d" % int(summary.get("citation_mismatch_delta") or 0))
    click.echo("New failures: %s" % summary["new_failures"])
    click.echo("Resolved failures: %s" % summary["resolved_failures"])
    click.echo("Added claims: %s" % summary["added_claims"])
    click.echo("Removed claims: %s" % summary["removed_claims"])
    click.echo("Changed claims: %s" % summary["changed_claims"])
    click.echo("New root causes: %s" % (", ".join(summary.get("new_root_causes") or []) or "none"))
    if written_report:
        click.echo("Report: %s" % written_report)
    for message in fail_messages:
        click.echo("Comparison failed: %s" % message, err=True)
    return 1 if fail_messages else 0


@cli.command("audit")
@click.argument("trace_json")
@click.option("--corpus", "corpus_path", required=True, help="Local corpus directory or file to search for supporting evidence.")
@click.option("--json", "json_output", is_flag=True, help="Print the full audit result as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML retrieval audit report.")
@click.option("--out", default=None, help="HTML report path. Implies --report when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml"]), help="Evidence scoring mode.")
@click.option("--fail-on", multiple=True, help="Fail on retrieval_miss, reranking_failure, chunking_issue, corpus_gap, answer_overreach, stale_source, insufficient_context, or any_failure.")
def audit_command(
    trace_json: str,
    corpus_path: str,
    json_output: bool,
    report: bool,
    out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
) -> int:
    """Audit a verified trace against a broader local corpus."""

    try:
        trace = load_trace_file(trace_json)
        result = audit_trace(trace, corpus_path=corpus_path, mode=mode)
    except VerificationInputError as exc:
        raise click.ClickException(str(exc)) from exc

    written_report = None
    if report or out:
        default_name = "%s_audit.html" % Path(trace_json).stem
        output_path = out or str(Path(".contexttrace") / "reports" / default_name)
        written_report = AuditReportGenerator().generate(result, trace, path=output_path)

    fail_messages = audit_failures(result, fail_on)
    if json_output:
        if written_report:
            click.echo("Report: %s" % written_report, err=True)
        click.echo(json.dumps(result, indent=2))
        for message in fail_messages:
            click.echo("Audit failed: %s" % message, err=True)
        return 1 if fail_messages else 0

    summary = result["summary"]
    click.echo("Primary audit label: %s" % summary["primary_audit_label"])
    click.echo("Claims audited: %s" % summary["total_claims"])
    click.echo("Corpus documents: %s" % summary["corpus_documents"])
    click.echo("Retrieval misses: %s" % summary["retrieval_miss"])
    click.echo("Chunking issues: %s" % summary["chunking_issue"])
    click.echo("Reranking failures: %s" % summary["reranking_failure"])
    click.echo("Corpus gaps: %s" % summary["corpus_gap"])
    click.echo("Answer overreach: %s" % summary["answer_overreach"])
    click.echo("Insufficient context: %s" % summary["insufficient_context"])
    stages = summary.get("failure_stages") or {}
    if stages:
        click.echo(
            "Failure stages: %s"
            % ", ".join("%s=%s" % (stage, count) for stage, count in sorted(stages.items()))
        )
    actions = list(summary.get("top_recommended_actions") or [])
    if actions:
        click.echo("Top actions:")
        for action in actions[:3]:
            click.echo("- %s claim(s): %s" % (action.get("claims"), action.get("action")))
    if written_report:
        click.echo("Report: %s" % written_report)
    for message in fail_messages:
        click.echo("Audit failed: %s" % message, err=True)
    return 1 if fail_messages else 0


@cli.group("capture")
def capture_group() -> None:
    """Capture RAG artifacts into portable verification traces."""


@capture_group.command("endpoint")
@click.option("--endpoint", default=None, help="RAG endpoint URL. Defaults to config eval_endpoint.")
@click.option("--query", required=True, help="Question to send to the RAG endpoint.")
@click.option("--method", default="POST", type=click.Choice(["GET", "POST"], case_sensitive=False), help="Endpoint method.")
@click.option("--input-key", default="question", show_default=True, help="Request body/query key for the question.")
@click.option("--answer-path", default="$.answer", show_default=True, help="JSONPath for answer extraction.")
@click.option("--contexts-path", default="$.contexts", show_default=True, help="JSONPath for context extraction.")
@click.option("--citations-path", default="$.citations", show_default=True, help="JSONPath for citation extraction.")
@click.option("--metadata-path", default="$.metadata", show_default=True, help="JSONPath for response metadata extraction.")
@click.option("--body-template", default=None, help="JSON body template. Use {{query}} where the question should be inserted.")
@click.option("--endpoint-header", multiple=True, help="Header formatted as Name:Value. May be repeated.")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Request timeout.")
@click.option("--out", default=".contexttrace/traces/captured_endpoint_trace.json", show_default=True, help="Portable trace JSON output path.")
@click.option("--verify", "verify_output", is_flag=True, help="Run claim-level verification after capture.")
@click.option("--json", "json_output", is_flag=True, help="Print capture output as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML verification report. Implies --verify.")
@click.option("--report-out", default=None, help="HTML report path. Implies --report and --verify when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml", "judge"]), help="Evidence scoring mode when verifying.")
@click.option("--judge-provider", default=None, help="Judge provider for --mode judge, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers; prefer CONTEXTTRACE_JUDGE_API_KEY in CI.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.option("--fail-on", multiple=True, help="Verification fail rule. Implies --verify.")
@click.pass_context
def capture_endpoint_command(
    ctx: click.Context,
    endpoint: Optional[str],
    query: str,
    method: str,
    input_key: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    metadata_path: str,
    body_template: Optional[str],
    endpoint_header: tuple[str, ...],
    timeout: float,
    out: str,
    verify_output: bool,
    json_output: bool,
    report: bool,
    report_out: Optional[str],
    mode: str,
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
    fail_on: tuple[str, ...],
) -> int:
    """Capture one live endpoint response as `contexttrace verify` JSON."""

    config = _load(ctx)
    resolved_endpoint = endpoint or config.eval_endpoint
    if not resolved_endpoint:
        raise click.ClickException("--endpoint or eval_endpoint in contexttrace.yaml is required.")
    try:
        body = json.loads(body_template) if body_template else None
        captured = capture_endpoint_trace(
            endpoint=resolved_endpoint,
            query=query,
            method=method,
            headers=_parse_headers(list(endpoint_header)),
            body_template=body,
            input_key=input_key,
            answer_path=answer_path,
            contexts_path=contexts_path,
            citations_path=citations_path,
            metadata_path=metadata_path,
            timeout=timeout,
        )
        written_trace = write_rag_trace(captured.trace, out)
    except (RuntimeError, ValueError, VerificationInputError) as exc:
        raise click.ClickException(str(exc)) from exc

    return _finish_capture_command(
        captured.trace,
        written_trace=written_trace,
        verify_output=verify_output,
        json_output=json_output,
        report=report,
        report_out=report_out,
        mode=mode,
        judge=_judge_from_cli(
            ctx,
            mode=mode,
            provider=judge_provider,
            base_url=judge_base_url,
            api_key=judge_api_key,
            model=judge_model,
        ),
        fail_on=fail_on,
    )


@capture_group.command("response")
@click.argument("response_json")
@click.option("--query", required=True, help="Question that produced the saved RAG response.")
@click.option("--answer-path", default="$.answer", show_default=True, help="JSONPath for answer extraction.")
@click.option("--contexts-path", default="$.contexts", show_default=True, help="JSONPath for context extraction.")
@click.option("--citations-path", default="$.citations", show_default=True, help="JSONPath for citation extraction.")
@click.option("--metadata-path", default="$.metadata", show_default=True, help="JSONPath for response metadata extraction.")
@click.option("--out", default=".contexttrace/traces/captured_response_trace.json", show_default=True, help="Portable trace JSON output path.")
@click.option("--verify", "verify_output", is_flag=True, help="Run claim-level verification after capture.")
@click.option("--json", "json_output", is_flag=True, help="Print capture output as JSON.")
@click.option("--report", is_flag=True, help="Generate a local HTML verification report. Implies --verify.")
@click.option("--report-out", default=None, help="HTML report path. Implies --report and --verify when provided.")
@click.option("--mode", default="lexical", show_default=True, type=click.Choice(["lexical", "semantic", "local_ml", "local-ml", "judge"]), help="Evidence scoring mode when verifying.")
@click.option("--judge-provider", default=None, help="Judge provider for --mode judge, for example ollama or local_openai.")
@click.option("--judge-base-url", default=None, help="Judge base URL. Defaults are local for ollama/local_openai/lmstudio/vllm.")
@click.option("--judge-api-key", default=None, help="Judge API key. Optional for local providers; prefer CONTEXTTRACE_JUDGE_API_KEY in CI.")
@click.option("--judge-model", default=None, help="Judge model name.")
@click.option("--fail-on", multiple=True, help="Verification fail rule. Implies --verify.")
@click.pass_context
def capture_response_command(
    ctx: click.Context,
    response_json: str,
    query: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    metadata_path: str,
    out: str,
    verify_output: bool,
    json_output: bool,
    report: bool,
    report_out: Optional[str],
    mode: str,
    judge_provider: Optional[str],
    judge_base_url: Optional[str],
    judge_api_key: Optional[str],
    judge_model: Optional[str],
    fail_on: tuple[str, ...],
) -> int:
    """Capture a saved RAG endpoint response as `contexttrace verify` JSON."""

    try:
        raw = Path(response_json).read_text(encoding="utf-8")
        response = json.loads(raw)
        captured = capture_response_trace(
            response=response,
            query=query,
            response_source=response_json,
            answer_path=answer_path,
            contexts_path=contexts_path,
            citations_path=citations_path,
            metadata_path=metadata_path,
        )
        written_trace = write_rag_trace(captured.trace, out)
    except OSError as exc:
        raise click.ClickException("Could not read response file %s: %s" % (response_json, exc)) from exc
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            "Invalid JSON in %s at line %s column %s: %s"
            % (response_json, exc.lineno, exc.colno, exc.msg)
        ) from exc
    except (ValueError, VerificationInputError) as exc:
        raise click.ClickException(str(exc)) from exc

    return _finish_capture_command(
        captured.trace,
        written_trace=written_trace,
        verify_output=verify_output,
        json_output=json_output,
        report=report,
        report_out=report_out,
        mode=mode,
        judge=_judge_from_cli(
            ctx,
            mode=mode,
            provider=judge_provider,
            base_url=judge_base_url,
            api_key=judge_api_key,
            model=judge_model,
        ),
        fail_on=fail_on,
    )


def _finish_capture_command(
    trace: object,
    *,
    written_trace: str,
    verify_output: bool,
    json_output: bool,
    report: bool,
    report_out: Optional[str],
    mode: str,
    fail_on: tuple[str, ...],
    judge: object = None,
) -> int:
    should_verify = verify_output or report or report_out is not None or bool(fail_on)
    verification = verify_trace(trace, mode=mode, judge=judge) if should_verify else None
    written_report = None
    if verification is not None:
        written_report = _write_verify_report(
            verification,
            trace,
            report=report,
            out=report_out,
            default_name="%s_verify.html" % Path(written_trace).stem,
        )

    if json_output:
        payload = {
            "trace_path": written_trace,
            "trace": trace.to_dict(),
        }
        if verification is not None:
            payload["verification"] = verification
        if written_report:
            payload["report_path"] = written_report
        click.echo(json.dumps(payload, indent=2))
        fail_messages = _verify_failures(verification or {}, fail_on)
        for message in fail_messages:
            click.echo("Verification failed: %s" % message, err=True)
        return 1 if fail_messages else 0

    click.echo("Trace: %s" % written_trace)
    if verification is None:
        return 0
    return _print_verify_result(
        verification,
        json_output=False,
        written_report=written_report,
        fail_on=fail_on,
    )


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
    judge_provider = str(config.judge_provider or "local").strip().lower().replace("-", "_")
    if judge_provider == "openai":
        checks.append(("judge API key present", bool(config.judge_api_key or os.getenv("OPENAI_API_KEY"))))
    else:
        checks.append(("judge API key present", True))
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


def _print_suite_result(
    result: dict,
    *,
    written_result: str,
    written_report: Optional[str],
) -> None:
    summary = result.get("summary") or {}
    click.echo("Suite: %s" % result.get("suite_name"))
    click.echo("Status: %s" % summary.get("status"))
    click.echo("Cases: %s" % summary.get("total_cases"))
    click.echo("Passed: %s" % summary.get("passed"))
    click.echo("Failed: %s" % summary.get("failed"))
    click.echo("Errors: %s" % summary.get("errors"))
    click.echo("Regressions: %s" % summary.get("regressions"))
    click.echo("Resolved failures: %s" % summary.get("resolved_failures"))
    click.echo("Average support rate: %.3f" % float(summary.get("average_support_rate") or 0.0))
    click.echo("Results: %s" % written_result)
    if written_report:
        click.echo("Report: %s" % written_report)

    failed_cases = [case for case in result.get("cases") or [] if case.get("status") in {"failed", "error"}]
    if failed_cases:
        click.echo("Failed cases:")
        for case in failed_cases:
            failures = "; ".join(str(item) for item in case.get("failures") or []) or "unknown failure"
            click.echo("- %s: %s" % (case.get("id"), failures))


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:80] or "contexttrace"


def _load(ctx: click.Context) -> ContextTraceConfig:
    return load_config(config_path=(ctx.obj or {}).get("config_path"))


def _judge_from_cli(
    ctx: click.Context,
    *,
    mode: str,
    provider: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
) -> object:
    if mode != "judge":
        return None
    config = _load(ctx)
    try:
        judge = build_judge_provider(
            provider=provider or config.judge_provider,
            base_url=base_url or config.judge_base_url,
            api_key=api_key or config.judge_api_key,
            model=model or config.judge_model,
            timeout=config.timeout,
            offline_strict=config.local_only,
            cache_enabled=config.judge_cache_enabled,
            cache_path=config.judge_cache_path,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if judge is None:
        raise click.ClickException(
            "--mode judge requires a judge provider such as ollama, local_openai, "
            "lmstudio, vllm, or openai. For local mode, try "
            "CONTEXTTRACE_JUDGE_PROVIDER=ollama."
        )
    return judge


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
