"""Fail-closed validation for the reviewed pre-acquisition source catalog."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit


EXPECTED_GROUPS = {
    "software_product_documentation",
    "policy_regulatory",
    "support_operational",
}
SHA1_PATTERN = re.compile(r"^[a-f0-9]{40}$")


class CatalogError(ValueError):
    """The catalog is unsafe or incomplete."""


def _unique(entries: list[Mapping[str, Any]], field: str) -> set[str]:
    values = [str(entry.get(field) or "") for entry in entries]
    if any(not value for value in values):
        raise CatalogError(f"Every catalog entry requires {field}.")
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise CatalogError(f"Duplicate {field}: {duplicates}")
    return set(values)


def validate_catalog(
    catalog: Mapping[str, Any],
    calibration_registry: Mapping[str, Any],
    *,
    require_attestation: bool = False,
) -> dict[str, Any]:
    if catalog.get("corpus_content_acquired") is not False:
        raise CatalogError("Pre-acquisition catalog cannot claim acquired content.")
    if catalog.get("paid_generation_started") is not False:
        raise CatalogError("Pre-acquisition catalog cannot claim paid generation.")

    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 36:
        raise CatalogError("Catalog requires exactly 36 source families.")
    family_ids = _unique(entries, "family_id")
    source_families = _unique(entries, "source_family")
    domain_ids = _unique(entries, "domain_id")
    canonical_urls = _unique(entries, "canonical_url")
    if family_ids != source_families:
        raise CatalogError("family_id and source_family sets must match exactly.")

    group_counts = Counter(str(entry.get("domain_group")) for entry in entries)
    if set(group_counts) != EXPECTED_GROUPS or any(
        group_counts[group] != 12 for group in EXPECTED_GROUPS
    ):
        raise CatalogError(f"Each domain group requires 12 families: {group_counts}")

    target_cases = sum(int(entry.get("target_cases") or 0) for entry in entries)
    if target_cases != int(catalog.get("natural_ood_target_cases") or -1):
        raise CatalogError("Entry target cases do not match catalog target.")
    if target_cases != 396:
        raise CatalogError("Reviewed Natural OOD allocation must total 396.")

    license_profiles = catalog.get("license_profiles")
    access_profiles = catalog.get("access_profiles")
    if not isinstance(license_profiles, dict) or not isinstance(access_profiles, dict):
        raise CatalogError("Catalog requires license and access profiles.")

    for entry in entries:
        family = str(entry["family_id"])
        license_profile = license_profiles.get(entry.get("license_profile"))
        access_profile = access_profiles.get(entry.get("access_profile"))
        if not isinstance(license_profile, dict):
            raise CatalogError(f"{family} references an unknown license profile.")
        if license_profile.get("review_status") != "approved":
            raise CatalogError(f"{family} license review is not approved.")
        if not str(license_profile.get("hosted_model_transmission") or "").startswith(
            "permitted"
        ):
            raise CatalogError(f"{family} is not approved for hosted transmission.")
        if not isinstance(access_profile, dict):
            raise CatalogError(f"{family} references an unknown access profile.")
        if access_profile.get("review_status") != "approved":
            raise CatalogError(f"{family} access review is not approved.")
        if access_profile.get("access_class") != "public":
            raise CatalogError(f"{family} is not public.")
        if access_profile.get("authentication_required") is not False:
            raise CatalogError(f"{family} unexpectedly requires authentication.")

        if entry["access_profile"] in {
            "github_commit_archive",
            "gitlab_commit_archive",
        }:
            commit = str(entry.get("commit_sha1") or "")
            if not SHA1_PATTERN.fullmatch(commit):
                raise CatalogError(f"{family} lacks an immutable commit SHA-1.")
            if commit not in str(entry["canonical_url"]):
                raise CatalogError(f"{family} canonical URL is not commit-pinned.")
            if not str(entry.get("content_root") or ""):
                raise CatalogError(f"{family} lacks a documentation content root.")
        elif entry["access_profile"] == "ecfr_versioner_api":
            snapshot_date = str(entry.get("snapshot_date") or "")
            title = int(entry.get("title") or 0)
            part = int(entry.get("part") or 0)
            parsed = urlsplit(str(entry["canonical_url"]))
            query = parse_qs(parsed.query)
            if (
                not re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date)
                or title < 1
                or part < 1
                or f"/full/{snapshot_date}/title-{title}.xml" not in parsed.path
                or query.get("part") != [str(part)]
            ):
                raise CatalogError(f"{family} has an invalid eCFR snapshot URL.")
        else:
            raise CatalogError(f"{family} uses an unsupported access profile.")

    calibration_sources = calibration_registry.get("sources")
    if not isinstance(calibration_sources, list) or not calibration_sources:
        raise CatalogError("Calibration registry is empty.")
    calibration_families = {
        str(source.get("source_family") or "") for source in calibration_sources
    }
    calibration_domains = {
        str(source.get("domain_id") or "") for source in calibration_sources
    }
    calibration_urls = {
        str(source.get("source_url") or "") for source in calibration_sources
    } | {
        str(source.get("canonical_identifier") or "")
        for source in calibration_sources
    }
    overlaps = {
        "source_family": sorted(source_families & calibration_families),
        "domain_id": sorted(domain_ids & calibration_domains),
        "canonical_url": sorted(canonical_urls & calibration_urls),
    }
    overlaps = {key: value for key, value in overlaps.items() if value}
    if overlaps:
        raise CatalogError(f"Calibration overlap detected: {overlaps}")

    calibration_status = catalog.get("calibration_registry")
    if not isinstance(calibration_status, dict):
        raise CatalogError("Catalog lacks calibration-registry status.")
    if int(calibration_status.get("read_errors") or 0) != 0:
        raise CatalogError("Calibration inventory contains read errors.")
    attested = calibration_status.get("external_human_exposure_attested") is True
    if require_attestation and not attested:
        raise CatalogError("External human-exposure attestation is still required.")

    return {
        "entry_count": len(entries),
        "domain_group_counts": dict(sorted(group_counts.items())),
        "target_cases": target_cases,
        "calibration_source_count": len(calibration_sources),
        "overlaps": overlaps,
        "external_human_exposure_attested": attested,
        "ready_for_acquisition_decision": attested,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/pre_acquisition_catalog.json"
        ),
    )
    parser.add_argument(
        "--calibration-registry",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/calibration/registry.json"),
    )
    parser.add_argument("--require-attestation", action="store_true")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    calibration = json.loads(
        args.calibration_registry.read_text(encoding="utf-8")
    )
    result = validate_catalog(
        catalog,
        calibration,
        require_attestation=args.require_attestation,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
