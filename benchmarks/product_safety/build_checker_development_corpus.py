"""Generate the source-family-disjoint learned-checker development corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "checker_development_cases.json"
BUILDER_VERSION = "contexttrace-checker-development-builder-v1.0.0"
SPLITS = ("train", "train", "train", "train", "validation", "test")


def build_corpus() -> dict[str, Any]:
    seeds = _seeds()
    cases: list[dict[str, Any]] = []
    for seed in seeds:
        supported = seed["supported_claim"]
        old = seed["old"]
        new = seed["new"]
        if supported.count(old) != 1:
            raise ValueError(f"{seed['id']} must contain its mutation source once.")
        negative = supported.replace(old, new, 1)
        common = {
            "category": seed["category"],
            "query": seed["query"],
            "premise": seed["premise"],
            "source_family": seed["source_family"],
            "split": seed["split"],
        }
        cases.extend(
            [
                {
                    **common,
                    "id": f"{seed['id']}__positive",
                    "claim": supported,
                    "label": 1,
                },
                {
                    **common,
                    "id": f"{seed['id']}__negative",
                    "claim": negative,
                    "label": 0,
                },
            ]
        )
    _assert_disjoint(cases)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "builder_version": BUILDER_VERSION,
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "cases": cases,
        "counts": {
            split: sum(case["split"] == split for case in cases)
            for split in ("train", "validation", "test")
        },
    }
    payload["payload_sha256"] = _canonical_sha256(payload)
    return payload


def _seeds() -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    category_rows = {
        "numeric": [
            ("retention", "The retention period is 30 days.", "30", "90"),
            ("timeout", "The request timeout is 15 seconds.", "15", "45"),
            ("backup", "Backups are retained for 14 days.", "14", "60"),
            ("quota", "The account quota is 100 requests.", "100", "500"),
            ("cache", "The cache lifetime is 20 minutes.", "20", "50"),
            ("archive", "Archives remain available for 7 years.", "7", "9"),
        ],
        "date": [
            (
                "policy",
                "The policy takes effect on July 1, 2026.",
                "July 1",
                "October 1",
            ),
            (
                "filing",
                "The filing deadline is March 15, 2027.",
                "March 15",
                "April 15",
            ),
            (
                "migration",
                "Migration begins on August 10, 2026.",
                "August 10",
                "September 10",
            ),
            ("renewal", "Renewal opens on January 5, 2027.", "January 5", "February 5"),
            ("audit", "The audit starts on May 20, 2026.", "May 20", "June 20"),
            (
                "release",
                "The release ships on November 2, 2026.",
                "November 2",
                "December 2",
            ),
        ],
        "version": [
            ("client", "Clients must use API v2.4.", "v2.4", "v3.0"),
            ("schema", "The schema version is v1.8.", "v1.8", "v2.1"),
            ("runtime", "The runtime requires v4.2.", "v4.2", "v5.0"),
            ("protocol", "The protocol uses v3.7.", "v3.7", "v4.0"),
            ("format", "The export format is v2.2.", "v2.2", "v2.9"),
            ("agent", "The agent targets API v6.1.", "v6.1", "v7.0"),
        ],
        "negation": [
            (
                "logging",
                "Audit logging is enabled by default.",
                "is enabled",
                "is not enabled",
            ),
            (
                "encryption",
                "Transport encryption is required.",
                "is required",
                "is not required",
            ),
            ("deletion", "Record deletion is allowed.", "is allowed", "is not allowed"),
            ("export", "Data export is permitted.", "is permitted", "is not permitted"),
            ("caching", "Response caching is active.", "is active", "is not active"),
            ("access", "Guest access is disabled.", "is disabled", "is not disabled"),
        ],
        "reversed_relation": [
            (
                "services",
                "Service A calls Service B.",
                "Service A calls Service B",
                "Service B calls Service A",
            ),
            (
                "workers",
                "Worker X invokes Worker Y.",
                "Worker X invokes Worker Y",
                "Worker Y invokes Worker X",
            ),
            (
                "queues",
                "Queue A sends Queue B.",
                "Queue A sends Queue B",
                "Queue B sends Queue A",
            ),
            (
                "stores",
                "Store A writes Store B.",
                "Store A writes Store B",
                "Store B writes Store A",
            ),
            (
                "agents",
                "Agent A calls Agent B.",
                "Agent A calls Agent B",
                "Agent B calls Agent A",
            ),
            (
                "jobs",
                "Job A creates Job B.",
                "Job A creates Job B",
                "Job B creates Job A",
            ),
        ],
        "identifier_substitution": [
            ("sdk", "The SDK supports JSON.", "JSON", "YAML"),
            ("api", "The API accepts XML.", "XML", "CSV"),
            ("cli", "The CLI emits TOML.", "TOML", "JSON"),
            ("etl", "The ETL job reads CSV.", "CSV", "XML"),
            ("ide", "The IDE imports YAML.", "YAML", "TOML"),
            ("cdn", "The CDN serves AVIF.", "AVIF", "PNG"),
        ],
        "path_substitution": [
            (
                "search",
                "The replacement endpoint is /v2/search.",
                "/v2/search",
                "/v1/search",
            ),
            ("users", "User creation uses /v3/users.", "/v3/users", "/v2/users"),
            ("events", "Events are posted to /api/events.", "/api/events", "/api/logs"),
            (
                "health",
                "Health checks use /status/health.",
                "/status/health",
                "/status/live",
            ),
            ("export", "Exports use /v4/export.", "/v4/export", "/v4/import"),
            (
                "tokens",
                "Tokens are issued at /oauth/token.",
                "/oauth/token",
                "/oauth/revoke",
            ),
        ],
        "status": [
            ("endpoint", "The endpoint is active.", "active", "deprecated"),
            ("schema", "The schema is current.", "current", "superseded"),
            ("feature", "The feature is enabled.", "enabled", "disabled"),
            ("connector", "The connector is deprecated.", "deprecated", "active"),
            ("policy", "The policy is superseded.", "superseded", "current"),
            ("integration", "The integration is disabled.", "disabled", "enabled"),
        ],
        "condition_omission": [
            (
                "refund",
                "Refunds are available if the item is unopened.",
                " if the item is unopened",
                "",
            ),
            (
                "retry",
                "Retries occur if the request times out.",
                " if the request times out",
                "",
            ),
            ("access", "Access is granted if MFA succeeds.", " if MFA succeeds", ""),
            (
                "backup",
                "A backup runs if replication fails.",
                " if replication fails",
                "",
            ),
            (
                "alert",
                "An alert fires if latency exceeds the limit.",
                " if latency exceeds the limit",
                "",
            ),
            (
                "renewal",
                "Renewal is allowed if payment clears.",
                " if payment clears",
                "",
            ),
        ],
        "scope_omission": [
            (
                "encryption",
                "Encryption is optional for local development.",
                " for local development",
                "",
            ),
            (
                "feature",
                "The feature is enabled for beta users.",
                " for beta users",
                "",
            ),
            (
                "support",
                "Priority support is available for enterprise accounts.",
                " for enterprise accounts",
                "",
            ),
            (
                "delete",
                "Deletion is available for administrators.",
                " for administrators",
                "",
            ),
            (
                "cache",
                "Caching is optional for local development.",
                " for local development",
                "",
            ),
            (
                "preview",
                "Preview access is enabled for beta users.",
                " for beta users",
                "",
            ),
        ],
        "numeric_boundary": [
            ("request", "Requests under 10 MB are accepted.", "under 10", "of 10"),
            ("latency", "Latency below 50 ms is healthy.", "below 50", "of 50"),
            ("quota", "Usage up to 100 GB is included.", "up to 100", "of 100"),
            ("age", "Accounts under 30 days old are restricted.", "under 30", "of 30"),
            ("batch", "Batches below 500 items are processed.", "below 500", "of 500"),
            ("price", "Plans under 20 dollars qualify.", "under 20", "of 20"),
        ],
        "temporal_boundary": [
            ("endpoint", "The endpoint was deprecated after v2.", "after v2", "in v2"),
            ("client", "The client was removed after v4.", "after v4", "in v4"),
            ("format", "The format was introduced after v3.", "after v3", "in v3"),
            ("flag", "The flag is unavailable before v5.", "before v5", "in v5"),
            ("method", "The method changed after v7.", "after v7", "in v7"),
            ("schema", "The schema is invalid before v6.", "before v6", "in v6"),
        ],
    }
    for category, rows in category_rows.items():
        for index, (family, premise, old, new) in enumerate(rows):
            source_family = f"{category}:{family}"
            seeds.append(
                {
                    "id": source_family.replace(":", "__"),
                    "category": category,
                    "query": f"Verify the {family} claim.",
                    "premise": premise,
                    "supported_claim": premise,
                    "old": old,
                    "new": new,
                    "source_family": source_family,
                    "split": SPLITS[index],
                }
            )
    return seeds


def _assert_disjoint(cases: list[dict[str, Any]]) -> None:
    families: dict[str, set[str]] = {}
    for case in cases:
        families.setdefault(str(case["split"]), set()).add(str(case["source_family"]))
    splits = sorted(families)
    for index, left in enumerate(splits):
        for right in splits[index + 1 :]:
            overlap = families[left] & families[right]
            if overlap:
                raise ValueError(f"Source-family leakage between {left} and {right}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(build_corpus(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != rendered
        ):
            raise SystemExit("Checker development corpus is missing or stale.")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    return 0


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
