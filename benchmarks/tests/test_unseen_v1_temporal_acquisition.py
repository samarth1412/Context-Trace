from __future__ import annotations

import copy
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.acquire_temporal_sources import (
    TemporalAcquisitionError,
    deterministic_tar,
    expand_section_selector,
    load_json,
    normalize_wikitext,
    prepare_private_workspace,
    reconstruct_github,
    safe_zip_members,
    sha256_file,
    validate_authorization,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_pre_acquisition_catalog.json"
)
AUTHORIZATION_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_acquisition_authorization.json"
)
CALIBRATION_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/calibration/registry.json"
)
NATURAL_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"
)
MANIFEST_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_source_manifest.json"
)
LEDGER_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_acquisition_ledger.json"
)
VALIDATION_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_acquisition_validation.json"
)


def _authorization_inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load_json(CATALOG_PATH),
        load_json(AUTHORIZATION_PATH),
        load_json(CALIBRATION_PATH),
        load_json(NATURAL_PATH),
    )


def test_exact_hash_authorization_is_narrow_and_valid() -> None:
    catalog, authorization, calibration, natural = _authorization_inputs()
    validate_authorization(
        catalog_path=CATALOG_PATH,
        catalog=catalog,
        authorization=authorization,
        calibration=calibration,
        natural=natural,
    )
    assert (
        sha256_file(CATALOG_PATH)
        == "a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678"
    )


def test_authorization_rejects_any_downstream_permission() -> None:
    catalog, authorization, calibration, natural = _authorization_inputs()
    changed = copy.deepcopy(authorization)
    changed["scope"]["model_calls_authorized"] = True
    with pytest.raises(TemporalAcquisitionError, match="broadened"):
        validate_authorization(
            catalog_path=CATALOG_PATH,
            catalog=catalog,
            authorization=changed,
            calibration=calibration,
            natural=natural,
        )


def test_private_workspace_is_narrow_and_mode_0700(tmp_path: Path) -> None:
    workspace = tmp_path / ".tmp-contexttrace-unseen-v1-temporal-test"
    prepare_private_workspace(workspace)
    assert workspace.stat().st_mode & 0o777 == 0o700
    with pytest.raises(TemporalAcquisitionError, match="dedicated"):
        prepare_private_workspace(tmp_path / "ordinary-directory")


def test_deterministic_tar_round_trips_allowlisted_content() -> None:
    members = [
        ("legal/LICENSE", b"license"),
        ("content/docs/guide.rst", b"guide text"),
    ]
    first = deterministic_tar(members)
    second = deterministic_tar(list(reversed(members)))
    assert first == second
    text, hashes = reconstruct_github(first)
    assert "===== FILE: docs/guide.rst =====" in text
    assert set(hashes) == {"content/docs/guide.rst", "legal/LICENSE"}


def test_deterministic_tar_rejects_path_traversal() -> None:
    with pytest.raises(TemporalAcquisitionError, match="Unsafe archive"):
        deterministic_tar([("../outside", b"bad")])


def test_wikitext_normalization_excludes_nested_templates_references_and_media() -> None:
    source = """
    Lead [[Target|visible text]].
    {{outer|value={{nested|secret}}}}
    <ref>User:Example and a citation secret</ref>
    [[File:private.png|caption]]
    == Details ==
    Kept operational text.
    == References ==
    * [https://example.test should disappear]
    """
    normalized = normalize_wikitext(source)
    assert "visible text" in normalized
    assert "Kept operational text" in normalized
    assert "nested" not in normalized
    assert "User:Example" not in normalized
    assert "private.png" not in normalized
    assert "should disappear" not in normalized


def test_us_code_selector_expansion_handles_numeric_and_alphanumeric_ranges() -> None:
    assert expand_section_selector("15 USC 6501-6506") == [
        "6501",
        "6502",
        "6503",
        "6504",
        "6505",
        "6506",
    ]
    assert expand_section_selector("42 USC 1320d-1320d-9") == [
        "1320d",
        "1320d-1",
        "1320d-2",
        "1320d-3",
        "1320d-4",
        "1320d-5",
        "1320d-6",
        "1320d-7",
        "1320d-8",
        "1320d-9",
    ]


def test_us_code_identifier_dash_is_normalized_without_changing_selector() -> None:
    assert "1320d–1".replace("–", "-") in expand_section_selector(
        "42 USC 1320d-1320d-9"
    )


def test_zip_guard_rejects_traversal_and_oversized_metadata() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.xml", "<section/>")
    with pytest.raises(TemporalAcquisitionError, match="Unsafe OLRC"):
        safe_zip_members(buffer.getvalue())


def test_authorization_json_never_contains_credentials_or_account_metadata() -> None:
    authorization = json.dumps(load_json(AUTHORIZATION_PATH)).casefold()
    forbidden = ("api_key", "authorization_header", "account_id", "token")
    assert not any(value in authorization for value in forbidden)


def test_reconstruction_rejects_nondeterministic_archive_metadata() -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("content/guide.md")
        info.size = 4
        info.mtime = 1
        archive.addfile(info, io.BytesIO(b"text"))
    with pytest.raises(TemporalAcquisitionError, match="Unsafe repository"):
        reconstruct_github(buffer.getvalue())


def test_committed_temporal_acquisition_metadata_is_complete_and_call_free() -> None:
    manifest = load_json(MANIFEST_PATH)
    ledger = load_json(LEDGER_PATH)
    validation = load_json(VALIDATION_PATH)
    assert len(manifest["sources"]) == 37
    assert ledger["source_count"] == 37
    assert ledger["pair_count"] == 20
    assert len(ledger["pairs"]) == 20
    assert {item["status"] for item in ledger["pairs"]} == {"eligible"}
    for field in ("model_calls", "verifier_calls", "trace_count", "paid_endpoint_calls"):
        assert ledger[field] == 0
        assert validation["result"][field] == 0
    assert validation["status"] == "valid"
    assert validation["result"]["prior_normalized_hash_collisions"] == []
    assert validation["result"]["wikimedia_user_metadata_records"] == 0


def test_validation_input_hashes_match_committed_integrity_records() -> None:
    validation = load_json(VALIDATION_PATH)
    inputs = validation["inputs"]
    assert inputs["catalog_sha256"] == sha256_file(CATALOG_PATH)
    assert inputs["authorization_sha256"] == sha256_file(AUTHORIZATION_PATH)
    assert inputs["source_manifest_sha256"] == sha256_file(MANIFEST_PATH)
    assert inputs["acquisition_ledger_sha256"] == sha256_file(LEDGER_PATH)
