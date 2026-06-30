from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

try:
    from benchmarks.contexttrace_bench.simulated_review.common import (
        AGENTS,
        annotation_prompt,
        load_response_schema,
        request_sha256,
        rq4_prompt,
        validate_review_response,
        write_jsonl,
    )
except ModuleNotFoundError:  # pragma: no cover - direct execution
    from common import (  # type: ignore
        AGENTS,
        annotation_prompt,
        load_response_schema,
        request_sha256,
        rq4_prompt,
        validate_review_response,
        write_jsonl,
    )


DEFAULT_MODEL = "gpt-4.1-nano-2025-04-14"
DEFAULT_BACKEND = "openai"
DEFAULT_MAX_CONCURRENCY = 8
DEFAULT_TIMEOUT = 120.0
MAX_ATTEMPTS = 3
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/chat"
PRICE_SOURCE = "https://openai.com/api/pricing/"
DEFAULT_INPUT_USD_PER_MILLION = 0.10
DEFAULT_OUTPUT_USD_PER_MILLION = 0.40


@dataclass(frozen=True)
class ReviewTask:
    case_id: str
    agent_id: str
    group: str
    system: str
    user: str


@dataclass
class ReviewResult:
    task: ReviewTask
    response: dict[str, Any] | None
    meta: dict[str, Any]
    failure: dict[str, Any] | None


async def request_review_with_retries(
    call: Callable[[str | None], Awaitable[tuple[str, dict[str, Any]]]],
    *,
    case_id: str,
    agent_id: str,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any] | None]:
    last_errors: list[str] = []
    aggregate = {"attempts": 0, "input_tokens": 0, "output_tokens": 0, "latency_seconds": 0.0}
    raw = ""
    for attempt in range(1, max_attempts + 1):
        aggregate["attempts"] = attempt
        feedback = "; ".join(last_errors) if last_errors else None
        started = time.perf_counter()
        try:
            raw, usage = await call(feedback)
            aggregate["latency_seconds"] += time.perf_counter() - started
            aggregate["input_tokens"] += int(usage.get("input_tokens") or 0)
            aggregate["output_tokens"] += int(usage.get("output_tokens") or 0)
            value = json.loads(raw)
            last_errors = validate_review_response(
                value, expected_case_id=case_id, expected_agent_id=agent_id
            )
            if not last_errors:
                return value, aggregate, None
        except (json.JSONDecodeError, ValueError, httpx.HTTPError) as exc:
            aggregate["latency_seconds"] += time.perf_counter() - started
            last_errors = [str(exc)]
        if attempt < max_attempts:
            await asyncio.sleep(min(2 ** (attempt - 1), 4))
    failure = {
        "case_id": case_id,
        "agent_id": agent_id,
        "attempts": max_attempts,
        "errors": last_errors,
        "raw_response": raw,
    }
    return None, aggregate, failure


class SimulatedReviewRunner:
    def __init__(
        self,
        *,
        backend: str,
        model: str,
        output_dir: Path,
        max_concurrency: int,
        timeout: float,
        input_usd_per_million: float,
        output_usd_per_million: float,
    ) -> None:
        if backend not in {"openai", "ollama"}:
            raise ValueError("backend must be openai or ollama")
        if backend == "openai" and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for the OpenAI backend.")
        self.backend = backend
        self.model = model
        self.output_dir = output_dir
        self.cache_dir = output_dir / ".cache"
        self.schema = load_response_schema()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self.input_usd_per_million = input_usd_per_million
        self.output_usd_per_million = output_usd_per_million

    async def close(self) -> None:
        await self.client.aclose()

    async def run(self, tasks: list[ReviewTask]) -> list[ReviewResult]:
        return await asyncio.gather(*(self._run_one(task) for task in tasks))

    async def _run_one(self, task: ReviewTask) -> ReviewResult:
        cache_path = self.cache_dir / task.group / task.agent_id / (task.case_id + ".json")
        request_hash = request_sha256(model=self.model, system=task.system, user=task.user)
        cached = _load_cache(cache_path, request_hash=request_hash)
        if cached is not None:
            return ReviewResult(
                task=task,
                response=cached.get("response"),
                meta={**dict(cached.get("meta") or {}), "cache_hit": True},
                failure=cached.get("failure"),
            )
        prior_meta: dict[str, Any] = {}
        if cache_path.is_file():
            prior = json.loads(cache_path.read_text(encoding="utf-8"))
            if prior.get("request_sha256") == request_hash and prior.get("failure") is not None:
                prior_meta = dict(prior.get("meta") or {})

        async with self.semaphore:
            async def call(feedback: str | None) -> tuple[str, dict[str, Any]]:
                return await self._request(task, feedback=feedback)

            response, usage, failure = await request_review_with_retries(
                call, case_id=task.case_id, agent_id=task.agent_id
            )
        for field in ("input_tokens", "output_tokens", "latency_seconds"):
            usage[field] = float(usage.get(field) or 0) + float(prior_meta.get(field) or 0)
        usage["attempts"] = int(usage.get("attempts") or 0) + int(prior_meta.get("attempts") or 0)
        meta = {
            **usage,
            "backend": self.backend,
            "model": self.model,
            "request_sha256": request_hash,
            "cache_hit": False,
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {"request_sha256": request_hash, "response": response, "failure": failure, "meta": meta},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return ReviewResult(task=task, response=response, meta=meta, failure=failure)

    async def _request(self, task: ReviewTask, *, feedback: str | None) -> tuple[str, dict[str, Any]]:
        user = task.user
        if feedback:
            user += (
                "\n\nYour previous output was invalid: %s. Return a corrected JSON object only. "
                "Use one minimal evidence span under 300 characters and keep the total response concise."
            ) % feedback
        if self.backend == "openai":
            headers = {
                "Authorization": "Bearer %s" % os.environ["OPENAI_API_KEY"],
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": task.system},
                    {"role": "user", "content": user},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "contexttrace_simulated_review",
                        "strict": True,
                        "schema": self.schema,
                    },
                },
                "temperature": 0,
                "max_completion_tokens": 900,
            }
            response = await self._post_with_rate_limit(OPENAI_ENDPOINT, headers=headers, payload=payload)
            body = response.json()
            message = body["choices"][0]["message"]
            if message.get("refusal"):
                raise ValueError("model refusal: %s" % message["refusal"])
            usage = body.get("usage") or {}
            return str(message.get("content") or ""), {
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
            }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": task.system},
                {"role": "user", "content": user},
            ],
            "format": self.schema,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 900},
        }
        response = await self.client.post(OLLAMA_ENDPOINT, json=payload)
        response.raise_for_status()
        body = response.json()
        return str((body.get("message") or {}).get("content") or ""), {
            "input_tokens": int(body.get("prompt_eval_count") or 0),
            "output_tokens": int(body.get("eval_count") or 0),
        }

    async def _post_with_rate_limit(
        self, endpoint: str, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> httpx.Response:
        response: httpx.Response | None = None
        for transport_attempt in range(1, 7):
            response = await self.client.post(endpoint, headers=headers, json=payload)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("retry-after")
            try:
                wait_seconds = float(retry_after) if retry_after else min(5 * transport_attempt, 30)
            except ValueError:
                wait_seconds = min(5 * transport_attempt, 30)
            await asyncio.sleep(max(1.0, min(wait_seconds, 60.0)))
        assert response is not None
        response.raise_for_status()
        return response

    def manifest(self, results: list[ReviewResult], *, task_type: str) -> dict[str, Any]:
        total_input = sum(int(row.meta.get("input_tokens") or 0) for row in results)
        total_output = sum(int(row.meta.get("output_tokens") or 0) for row in results)
        cache_hits = sum(bool(row.meta.get("cache_hit")) for row in results)
        failures = sum(row.failure is not None for row in results)
        cost = (
            total_input * self.input_usd_per_million / 1_000_000
            + total_output * self.output_usd_per_million / 1_000_000
            if self.backend == "openai"
            else 0.0
        )
        groups = {}
        for group in sorted({row.task.group for row in results}):
            group_rows = [row for row in results if row.task.group == group]
            group_input = sum(int(row.meta.get("input_tokens") or 0) for row in group_rows)
            group_output = sum(int(row.meta.get("output_tokens") or 0) for row in group_rows)
            group_cost = (
                group_input * self.input_usd_per_million / 1_000_000
                + group_output * self.output_usd_per_million / 1_000_000
                if self.backend == "openai"
                else 0.0
            )
            groups[group] = {
                "tasks": len(group_rows),
                "completed": sum(row.failure is None for row in group_rows),
                "input_tokens": group_input,
                "output_tokens": group_output,
                "estimated_cost_usd": round(group_cost, 6),
            }
        return {
            "schema_version": 1,
            "pilot_type": "llm_simulated_review_not_human_validation",
            "task_type": task_type,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "backend": self.backend,
            "model": self.model,
            "response_schema": "schemas/review_response.schema.json",
            "tasks": len(results),
            "completed": len(results) - failures,
            "parse_failures": failures,
            "cache_hits": cache_hits,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "estimated_cost_usd": round(cost, 6),
            "groups": groups,
            "price_snapshot": {
                "input_usd_per_million": self.input_usd_per_million,
                "output_usd_per_million": self.output_usd_per_million,
                "source": PRICE_SOURCE,
            },
            "human_review": False,
            "independent_review": False,
            "paper_result_eligible": False,
            "sota_gate_eligible": False,
        }


def build_annotation_tasks(packet: dict[str, Any], *, limit: int | None = None) -> list[ReviewTask]:
    cases = list(packet.get("cases") or [])
    if limit is not None:
        cases = cases[:limit]
    tasks = []
    for case in cases:
        for agent_id in AGENTS:
            system, user, _ = annotation_prompt(case, agent_id)
            tasks.append(
                ReviewTask(
                    case_id=str(case["blind_id"]),
                    agent_id=agent_id,
                    group="annotation",
                    system=system,
                    user=user,
                )
            )
    return tasks


def build_rq4_tasks(
    packet: dict[str, Any], key: dict[str, Any], *, limit: int | None = None
) -> list[ReviewTask]:
    key_index = {str(row["blind_id"]): row for row in key.get("cases") or []}
    cases = list(packet.get("cases") or [])
    if limit is not None:
        cases = cases[:limit]
    tasks = []
    for case in cases:
        case_id = str(case["blind_id"])
        key_row = key_index.get(case_id)
        if key_row is None:
            raise ValueError("RQ4 private key is missing %s" % case_id)
        condition_by_option = dict(key_row.get("condition_by_option") or {})
        core_option = _option_for_condition(condition_by_option, "semantic_core")
        evidence_option = _option_for_condition(condition_by_option, "evidence_chain")
        settings = {
            "raw_trace": None,
            "score_only": case[core_option],
            "contexttrace": case[evidence_option],
        }
        for setting, output in settings.items():
            for agent_id in AGENTS:
                system, user, _ = rq4_prompt(
                    case, agent_id=agent_id, setting=setting, evaluation_output=output
                )
                tasks.append(
                    ReviewTask(
                        case_id=case_id,
                        agent_id=agent_id,
                        group=setting,
                        system=system,
                        user=user,
                    )
                )
    return tasks


def write_outputs(
    results: list[ReviewResult], *, output_dir: Path, task_type: str, manifest: dict[str, Any]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = [row.failure for row in results if row.failure is not None]
    write_jsonl(output_dir / "parse_failures.jsonl", [row for row in failures if row is not None])
    if task_type == "annotation":
        for agent_id, config in AGENTS.items():
            rows = [
                row.response
                for row in results
                if row.task.agent_id == agent_id and row.response is not None
            ]
            write_jsonl(output_dir / str(config["file"]), [row for row in rows if row is not None])
    else:
        names = {
            "raw_trace": "setting_a_raw_trace.jsonl",
            "score_only": "setting_b_score_only.jsonl",
            "contexttrace": "setting_c_contexttrace.jsonl",
        }
        for group, filename in names.items():
            rows = [row.response for row in results if row.task.group == group and row.response is not None]
            write_jsonl(output_dir / filename, [row for row in rows if row is not None])
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    packet = _load_json(Path(args.packet))
    if args.command == "annotation":
        tasks = build_annotation_tasks(packet, limit=args.limit)
    else:
        key = _load_json(Path(args.key))
        tasks = build_rq4_tasks(packet, key, limit=args.limit)
    runner = SimulatedReviewRunner(
        backend=args.backend,
        model=args.model,
        output_dir=Path(args.output_dir),
        max_concurrency=args.max_concurrency,
        timeout=args.timeout,
        input_usd_per_million=args.input_usd_per_million,
        output_usd_per_million=args.output_usd_per_million,
    )
    try:
        results = await runner.run(tasks)
        manifest = runner.manifest(results, task_type=args.command)
        if args.command == "annotation":
            manifest["dataset"] = args.dataset
        write_outputs(results, output_dir=Path(args.output_dir), task_type=args.command, manifest=manifest)
        return manifest
    finally:
        await runner.close()


def _load_cache(path: Path, *, request_hash: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("request_sha256") != request_hash:
        return None
    if value.get("failure") is not None:
        return None
    response = value.get("response")
    if response is not None and validate_review_response(response):
        return None
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object." % path)
    return value


def _option_for_condition(mapping: dict[str, Any], condition: str) -> str:
    matches = [option for option, value in mapping.items() if value == condition]
    if len(matches) != 1:
        raise ValueError("Expected one %s option; found %s" % (condition, matches))
    return matches[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled LLM-simulated ARR review pilots.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("annotation", "rq4"):
        child = subparsers.add_parser(name)
        child.add_argument("--packet", required=True)
        child.add_argument("--output-dir", required=True)
        child.add_argument("--backend", choices=("openai", "ollama"), default=DEFAULT_BACKEND)
        child.add_argument("--model", default=DEFAULT_MODEL)
        child.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY)
        child.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
        child.add_argument("--limit", type=int, default=None)
        child.add_argument("--input-usd-per-million", type=float, default=DEFAULT_INPUT_USD_PER_MILLION)
        child.add_argument("--output-usd-per-million", type=float, default=DEFAULT_OUTPUT_USD_PER_MILLION)
    subparsers.choices["annotation"].add_argument("--dataset", required=True)
    subparsers.choices["rq4"].add_argument("--key", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.max_concurrency <= 0:
        raise ValueError("max-concurrency must be positive")
    manifest = asyncio.run(_run(args))
    print("Simulated review: %s" % manifest["pilot_type"])
    print("Completed: %s/%s" % (manifest["completed"], manifest["tasks"]))
    print("Parse failures: %s" % manifest["parse_failures"])
    print("Estimated cost USD: %.6f" % manifest["estimated_cost_usd"])
    return 0 if manifest["parse_failures"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
