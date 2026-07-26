"""Build the offline pre-acquisition lock for the temporal/source track.

The external identities in this file were machine-reviewed on 2026-07-26.
Building and validating the catalog performs no network, model, verifier, or
annotation calls and does not authorize acquisition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "1.0"
RECORD_KIND = "contexttrace_unseen_v1_temporal_pre_acquisition_catalog"
PAIR_TYPES = (
    "archived_policy_to_current_policy",
    "old_api_to_replacement_api",
    "noncanonical_to_canonical",
    "low_authority_to_authoritative",
)
PAIR_TYPE_CONDITIONS = {
    "archived_policy_to_current_policy": ("archived", "current"),
    "old_api_to_replacement_api": ("deprecated_api", "replacement_api"),
    "noncanonical_to_canonical": ("noncanonical", "canonical"),
    "low_authority_to_authoritative": ("low_authority", "authoritative"),
}
GOVINFO_TERMS = "https://www.govinfo.gov/about/policies"
WIKIMEDIA_TERMS = "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
ECFR_API_DOCS = "https://www.ecfr.gov/developers/documentation/api/v1"
OLRC_DOWNLOADS = "https://uscode.house.gov/download/download.shtml"


class TemporalCatalogError(ValueError):
    """The temporal pre-acquisition catalog is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _government_license() -> dict[str, Any]:
    return {
        "license_id": "US-Government-Work",
        "terms_url": GOVINFO_TERMS,
        "redistribution": "permitted",
        "attribution_required": True,
        "review_status": "machine_review_passed_owner_pending",
        "restrictions": [
            "retain issuing-body attribution",
            "exclude third-party copyrighted material and incorporated standards",
            "exclude images and separately licensed media",
        ],
    }


def _wikimedia_license() -> dict[str, Any]:
    return {
        "license_id": "CC-BY-SA-4.0",
        "terms_url": WIKIMEDIA_TERMS,
        "redistribution": "permitted",
        "attribution_required": True,
        "review_status": "machine_review_passed_owner_pending",
        "restrictions": [
            "retain page URL, revision ID, and author-history attribution link",
            "retain CC BY-SA notice for redistributed or modified text",
            "exclude non-text media and fair-use content",
            "exclude usernames, edit summaries, talk pages, and user metadata",
        ],
    }


REPOSITORY_LICENSES = {
    "scikit-learn/scikit-learn": {
        "license_id": "BSD-3-Clause",
        "terms_url": "https://github.com/scikit-learn/scikit-learn/blob/main/COPYING",
    },
    "matplotlib/matplotlib": {
        "license_id": "Matplotlib-1.3",
        "terms_url": "https://matplotlib.org/stable/project/license.html",
    },
    "scipy/scipy": {
        "license_id": "BSD-3-Clause",
        "terms_url": "https://github.com/scipy/scipy/blob/main/LICENSE.txt",
    },
    "imageio/imageio": {
        "license_id": "BSD-2-Clause",
        "terms_url": "https://github.com/imageio/imageio/blob/master/LICENSE",
    },
    "pytest-dev/pytest": {
        "license_id": "MIT",
        "terms_url": "https://github.com/pytest-dev/pytest/blob/main/LICENSE",
    },
    "python-pillow/Pillow": {
        "license_id": "HPND",
        "terms_url": "https://github.com/python-pillow/Pillow/blob/main/LICENSE",
    },
}


def _repository_license(repository: str) -> dict[str, Any]:
    identity = REPOSITORY_LICENSES[repository]
    return {
        **identity,
        "redistribution": "permitted",
        "attribution_required": True,
        "review_status": "machine_review_passed_owner_pending",
        "restrictions": [
            "retain repository license",
            "retain only allowlisted first-party documentation and docstrings",
            "exclude vendored, generated, binary, and third-party content",
        ],
    }


def _access() -> dict[str, Any]:
    return {
        "access_class": "public",
        "authentication_required": False,
        "collection_permitted": True,
        "hosted_model_transmission_permitted": True,
        "privacy_classification": "public",
    }


def _base_source(
    *,
    source_id: str,
    condition: str,
    source_family: str,
    domain_group: str,
    domain_id: str,
    publication_window: str,
    publisher: str,
    source_url: str,
    canonical_identifier: str,
    acquisition_method: str,
    immutable_revision: Mapping[str, Any],
    extraction: Mapping[str, Any],
    license_record: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "condition": condition,
        "source_family": source_family,
        "domain_group": domain_group,
        "domain_id": domain_id,
        "publication_window": publication_window,
        "publisher": publisher,
        "source_url": source_url,
        "canonical_identifier": canonical_identifier,
        "acquisition_method": acquisition_method,
        "immutable_revision": dict(immutable_revision),
        "extraction": dict(extraction),
        "license": dict(license_record),
        "access": _access(),
    }


ECFR_PAIRS = (
    {
        "slug": "coppa",
        "domain_id": "childrens_online_privacy_coppa",
        "title": 16,
        "part": 312,
        "old_date": "2020-01-01",
        "old_bytes": 39968,
        "old_sha256": "0a57819898dca97d0c97303c8f61e9f166eba5da0a9fc615f11bf3d9c80de965",
        "current_date": "2026-07-22",
        "current_bytes": 49580,
        "current_sha256": "e7de115eca9b7e8cd8851a2f3fb952c0fd510122fb92c41f00478034b7f38a43",
    },
    {
        "slug": "information_blocking",
        "domain_id": "health_information_blocking",
        "title": 45,
        "part": 171,
        "old_date": "2021-01-01",
        "old_bytes": 45367,
        "old_sha256": "7ec15d69de91a06f36e4f12ccc57707f2616bc302e7ffad068265bda4a4ae28b",
        "current_date": "2026-07-22",
        "current_bytes": 71529,
        "current_sha256": "881f03c2034c1a6b4d49e9cde4adf70a84182f5890eb1be66f4026f4c601e023",
    },
    {
        "slug": "workplace_safety",
        "domain_id": "general_industry_workplace_safety",
        "title": 29,
        "part": 1910,
        "old_date": "2020-01-01",
        "old_bytes": 7475282,
        "old_sha256": "23e87afb3bcd7aad37069deeb4c94e937101130a5e468dd9c55434e8d3678361",
        "current_date": "2026-07-22",
        "current_bytes": 6716342,
        "current_sha256": "65c51e3f40185c53864997402c82b3da81a1867f38c04562726b82f0d5e2c6ca",
    },
    {
        "slug": "hazardous_waste",
        "domain_id": "hazardous_waste_identification",
        "title": 40,
        "part": 261,
        "old_date": "2020-01-01",
        "old_bytes": 2086760,
        "old_sha256": "c2842f835e9b3c22c3caef51ed4e91d18401d30da13aca3e641c87e95ba34195",
        "current_date": "2026-07-22",
        "current_bytes": 2061265,
        "current_sha256": "930cc290d128d71122de4a81188ef2d57675d72021263b51ad05a6536cb285ad",
    },
    {
        "slug": "transport_airworthiness",
        "domain_id": "transport_aircraft_airworthiness",
        "title": 14,
        "part": 25,
        "old_date": "2020-01-01",
        "old_bytes": 1127205,
        "old_sha256": "ea8c2715ae41b9c676bbaa45d815884a89bdbe4505f42f7b32a334a2f9b7d7b4",
        "current_date": "2026-07-22",
        "current_bytes": 1147803,
        "current_sha256": "55e3b7d64af4cb293caaaf206963db3a58cdffb940c3b6f6c9b4ecce7294b742",
    },
)


API_PAIRS = (
    {
        "slug": "sklearn_feature_names",
        "domain_id": "machine_learning_preprocessing_api",
        "repository": "scikit-learn/scikit-learn",
        "old_ref": "1.0.2",
        "old_commit": "7e1e6d09bcc2eaeba98f7e737aac2ac782f0e5f1",
        "old_date": "2021-12-25T11:27:28Z",
        "old_paths": [
            "sklearn/preprocessing/_encoders.py",
            "doc/whats_new/v1.0.rst",
        ],
        "new_repository": "scikit-learn/scikit-learn",
        "new_ref": "1.2.0",
        "new_commit": "dc580a8ef5ee2a8aea80498388690e2213118efd",
        "new_date": "2022-12-08T12:04:29Z",
        "new_paths": [
            "sklearn/preprocessing/_encoders.py",
            "doc/whats_new/v1.2.rst",
        ],
        "relationship": (
            "Official 1.0 documentation deprecates get_feature_names and directs "
            "users to get_feature_names_out before removal in 1.2."
        ),
        "evidence_url": (
            "https://scikit-learn.org/1.0/modules/generated/"
            "sklearn.preprocessing.OneHotEncoder.html"
        ),
    },
    {
        "slug": "matplotlib_hist_density",
        "domain_id": "scientific_plotting_histogram_api",
        "repository": "matplotlib/matplotlib",
        "old_ref": "v2.2.0",
        "old_commit": "66e49f9a28f29b9a3a18cd4c6bfd5fdd1836eb0e",
        "old_date": "2018-03-05T05:07:21Z",
        "old_paths": ["lib/matplotlib/axes/_axes.py"],
        "new_repository": "matplotlib/matplotlib",
        "new_ref": "v3.1.0",
        "new_commit": "a8f4a742803b5238911b9c3f698f2417c3ac441a",
        "new_date": "2019-05-18T01:55:28Z",
        "new_paths": ["lib/matplotlib/axes/_axes.py"],
        "relationship": (
            "Official Matplotlib 2.2 documentation marks hist(normed=...) as "
            "deprecated and directs users to density=..., which is the replacement API."
        ),
        "evidence_url": (
            "https://matplotlib.org/2.2.0/api/_as_gen/matplotlib.pyplot.hist.html"
        ),
    },
    {
        "slug": "scipy_imageio_imread",
        "domain_id": "scientific_image_io_api",
        "repository": "scipy/scipy",
        "old_ref": "v1.2.0",
        "old_commit": "722bfc3f2cb4884c7ef3eb87cefcb91ff7479208",
        "old_date": "2018-12-17T17:54:00Z",
        "old_paths": [
            "scipy/misc/pilutil.py",
            "doc/source/misc.rst",
            "doc/release/1.2.0-notes.rst",
        ],
        "new_repository": "imageio/imageio",
        "new_ref": "v2.37.4",
        "new_commit": "671d96a5dd9bc94050cc89c4b436e2f7c874283e",
        "new_date": "2026-07-20T05:25:55Z",
        "new_paths": ["docs/reference/userapi.rst"],
        "relationship": (
            "Official SciPy documentation deprecates scipy.misc.imread and "
            "directs users to imageio.imread; the replacement is documented by ImageIO."
        ),
        "evidence_url": "https://docs.scipy.org/doc/scipy-1.2.0/reference/misc.html",
    },
    {
        "slug": "pytest_yield_fixture",
        "domain_id": "python_testing_fixture_api",
        "repository": "pytest-dev/pytest",
        "old_ref": "3.0.0",
        "old_commit": "c74ce371ab923edb990f40cf21f4309e1b4871ad",
        "old_date": "2016-08-18T16:02:01Z",
        "old_paths": ["doc/en/yieldfixture.rst", "_pytest/fixtures.py"],
        "new_repository": "pytest-dev/pytest",
        "new_ref": "6.2.5",
        "new_commit": "1569fac603d9a50022e1474b494eebf970a2a3af",
        "new_date": "2021-08-29T14:09:45Z",
        "new_paths": ["doc/en/deprecations.rst", "doc/en/yieldfixture.rst"],
        "relationship": (
            "Official pytest documentation identifies yield_fixture as a "
            "deprecated alias and directs users to pytest.fixture with yield."
        ),
        "evidence_url": "https://docs.pytest.org/en/7.1.x/deprecations.html",
    },
    {
        "slug": "pillow_resampling_lanczos",
        "domain_id": "python_imaging_resampling_api",
        "repository": "python-pillow/Pillow",
        "old_ref": "9.1.0",
        "old_commit": "5d070222d21138d2ead002fd33fdf5adcb708941",
        "old_date": "2022-04-01T07:48:32Z",
        "old_paths": ["docs/releasenotes/9.1.0.rst", "docs/deprecations.rst"],
        "new_repository": "python-pillow/Pillow",
        "new_ref": "10.0.0",
        "new_commit": "6e28ed1f36d0eb74053af54e1eddc9c29db698cd",
        "new_date": "2023-07-01T12:08:11Z",
        "new_paths": ["docs/releasenotes/10.0.0.rst", "docs/deprecations.rst"],
        "relationship": (
            "Official Pillow documentation records removal of Image.ANTIALIAS "
            "and directs users to Image.LANCZOS or Image.Resampling.LANCZOS."
        ),
        "evidence_url": "https://pillow.readthedocs.io/en/stable/deprecations.html",
    },
)


OLRC_TITLES = {
    5: {
        "bytes": 2942306,
        "sha256": "f725c011f1db669649e24154db5db5a290268a6a82588ccb68df3de94ff28dad",
        "selectors": ["5 USC 552"],
    },
    15: {
        "bytes": 5027552,
        "sha256": "aaf4eb0b69374ab160da244bec7f81348099016ae83ded905ded4722824e4851",
        "selectors": ["15 USC 6501-6506"],
    },
    17: {
        "bytes": 493323,
        "sha256": "8d8e29c944e7225d5cb6a74dbc125f9e8a49f098daadb29ee9376b0cbe43bbfa",
        "selectors": ["17 USC 107", "17 USC 512", "17 USC 1201"],
    },
    18: {
        "bytes": 1971101,
        "sha256": "2813d4e76e0bb148e708f6ce574246f16328ffe16f426624d357831e97bbd3d1",
        "selectors": ["18 USC 1030"],
    },
    29: {
        "bytes": 1832188,
        "sha256": "bf7cc70a4e11fc005c3d5b221cf764fb45115f5b9904445f089d4201ac5af28d",
        "selectors": ["29 USC 206", "29 USC 651-678"],
    },
    35: {
        "bytes": 277930,
        "sha256": "fb3a4ede2490dd5ea2a8193635d1b9dba564a596eceaf3ea3f293018a26f9b44",
        "selectors": ["35 USC 101"],
    },
    42: {
        "bytes": 18161570,
        "sha256": "31929c28f117362ac8788607242795769b05ed7726f07e4ed3b1786f39655ce7",
        "selectors": ["42 USC 1983", "42 USC 1320d-1320d-9"],
    },
}


WIKISOURCE_SOURCES = (
    {
        "slug": "foia_section",
        "domain_id": "freedom_of_information",
        "title": "United States Code/Title 5/Chapter 5/Section 552",
        "page_id": 354264,
        "revision_id": 13890117,
        "revision_timestamp": "2024-02-21T12:40:28Z",
        "length": 30748,
        "olrc_title": 5,
        "selector": "5 USC 552",
    },
    {
        "slug": "copyright_fair_use",
        "domain_id": "copyright_fair_use",
        "title": "United States Code/Title 17/Chapter 1/Section 107",
        "page_id": 14861,
        "revision_id": 14231081,
        "revision_timestamp": "2024-05-28T02:51:50Z",
        "length": 32376,
        "olrc_title": 17,
        "selector": "17 USC 107",
    },
    {
        "slug": "minimum_wage",
        "domain_id": "federal_minimum_wage",
        "title": "United States Code/Title 29/Chapter 8/Section 206",
        "page_id": 638156,
        "revision_id": 14227477,
        "revision_timestamp": "2024-05-26T23:41:10Z",
        "length": 9355,
        "olrc_title": 29,
        "selector": "29 USC 206",
    },
    {
        "slug": "patent_eligibility",
        "domain_id": "patent_eligibility",
        "title": "United States Code/Title 35/Chapter 10/Section 101",
        "page_id": 111438,
        "revision_id": 14305370,
        "revision_timestamp": "2024-06-30T01:31:19Z",
        "length": 2402,
        "olrc_title": 35,
        "selector": "35 USC 101",
    },
    {
        "slug": "civil_rights_action",
        "domain_id": "civil_rights_cause_of_action",
        "title": "United States Code/Title 42/Chapter 21/Section 1983",
        "page_id": 695212,
        "revision_id": 14227426,
        "revision_timestamp": "2024-05-26T23:35:30Z",
        "length": 1367,
        "olrc_title": 42,
        "selector": "42 USC 1983",
    },
)


WIKIPEDIA_SOURCES = (
    {
        "slug": "hipaa",
        "domain_id": "health_information_privacy",
        "title": "Health Insurance Portability and Accountability Act",
        "page_id": 384064,
        "revision_id": 1357830950,
        "revision_timestamp": "2026-06-04T22:52:18Z",
        "length": 74275,
        "olrc_title": 42,
        "selector": "42 USC 1320d-1320d-9",
    },
    {
        "slug": "coppa_summary",
        "domain_id": "childrens_online_privacy_statute",
        "title": "Children's Online Privacy Protection Act",
        "page_id": 53133,
        "revision_id": 1359675456,
        "revision_timestamp": "2026-06-16T15:36:54Z",
        "length": 61958,
        "olrc_title": 15,
        "selector": "15 USC 6501-6506",
    },
    {
        "slug": "osha_act_summary",
        "domain_id": "occupational_safety_statute",
        "title": "Occupational Safety and Health Act (United States)",
        "page_id": 461036,
        "revision_id": 1365514586,
        "revision_timestamp": "2026-07-22T23:15:04Z",
        "length": 24471,
        "olrc_title": 29,
        "selector": "29 USC 651-678",
    },
    {
        "slug": "dmca_summary",
        "domain_id": "digital_copyright_statute",
        "title": "Digital Millennium Copyright Act",
        "page_id": 20648089,
        "revision_id": 1358968889,
        "revision_timestamp": "2026-06-12T04:50:30Z",
        "length": 117647,
        "olrc_title": 17,
        "selector": "17 USC 512 and 1201",
    },
    {
        "slug": "cfaa_summary",
        "domain_id": "computer_fraud_statute",
        "title": "Computer Fraud and Abuse Act",
        "page_id": 276753,
        "revision_id": 1362897733,
        "revision_timestamp": "2026-07-06T22:03:05Z",
        "length": 47643,
        "olrc_title": 18,
        "selector": "18 USC 1030",
    },
)


def _ecfr_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for item in ECFR_PAIRS:
        family = f"temporal_ecfr_{item['slug']}"
        ids: list[str] = []
        for condition, date_key, hash_key, bytes_key in (
            ("archived", "old_date", "old_sha256", "old_bytes"),
            ("current", "current_date", "current_sha256", "current_bytes"),
        ):
            date = str(item[date_key])
            source_id = f"{family}_{condition}_{date.replace('-', '')}"
            url = (
                f"https://www.ecfr.gov/api/versioner/v1/full/{date}/"
                f"title-{item['title']}.xml?part={item['part']}"
            )
            sources.append(
                _base_source(
                    source_id=source_id,
                    condition=condition,
                    source_family=family,
                    domain_group="policy_regulatory",
                    domain_id=str(item["domain_id"]),
                    publication_window=date[:4],
                    publisher="Office of the Federal Register / GPO",
                    source_url=url,
                    canonical_identifier=(
                        f"ecfr:{date}:title-{item['title']}:part-{item['part']}"
                    ),
                    acquisition_method="ecfr_versioner_api",
                    immutable_revision={
                        "kind": "effective_date",
                        "value": date,
                        "expected_sha256": item[hash_key],
                        "expected_bytes": item[bytes_key],
                    },
                    extraction={
                        "format": "xml",
                        "selector": f"title {item['title']} part {item['part']}",
                        "exclude": [
                            "incorporated standards",
                            "images",
                            "editorial third-party material",
                        ],
                    },
                    license_record=_government_license(),
                )
            )
            ids.append(source_id)
        pairs.append(
            {
                "pair_id": f"ctu1_pair_archived_{item['slug']}",
                "pair_type": "archived_policy_to_current_policy",
                "left_source_id": ids[0],
                "right_source_id": ids[1],
                "left_condition": "archived",
                "right_condition": "current",
                "domain_group": "policy_regulatory",
                "domain_id": item["domain_id"],
                "planned_cases": 5,
                "authority_basis": (
                    "Both snapshots are official point-in-time eCFR Versioner API "
                    "responses; the later effective-date snapshot governs freshness."
                ),
                "authority_scope": (
                    "Currentness contrast within the same official regulatory "
                    "source; no claim of legal advice or ultimate legal effect."
                ),
                "material_relationship_basis": (
                    "Pre-acquisition byte and SHA-256 comparison confirms that the "
                    "official part changed between the pinned dates. Acquisition must "
                    "produce a structural XML diff before generation."
                ),
                "relationship_evidence_urls": [ECFR_API_DOCS],
            }
        )
    return sources, pairs


def _api_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for item in API_PAIRS:
        family = f"temporal_api_{item['slug']}"
        ids: list[str] = []
        for condition, repository_key, ref_key, commit_key, date_key, paths_key in (
            (
                "deprecated_api",
                "repository",
                "old_ref",
                "old_commit",
                "old_date",
                "old_paths",
            ),
            (
                "replacement_api",
                "new_repository",
                "new_ref",
                "new_commit",
                "new_date",
                "new_paths",
            ),
        ):
            repository = str(item[repository_key])
            commit = str(item[commit_key])
            source_id = f"{family}_{condition}"
            sources.append(
                _base_source(
                    source_id=source_id,
                    condition=condition,
                    source_family=family,
                    domain_group="software_product_documentation",
                    domain_id=str(item["domain_id"]),
                    publication_window=str(item[date_key])[:4],
                    publisher=repository.split("/", 1)[0],
                    source_url=f"https://github.com/{repository}/tree/{commit}",
                    canonical_identifier=f"github:{repository}@{commit}",
                    acquisition_method="github_raw_allowlist",
                    immutable_revision={
                        "kind": "git_commit",
                        "value": commit,
                        "release_ref": item[ref_key],
                        "commit_timestamp": item[date_key],
                    },
                    extraction={
                        "format": "utf-8_source_text",
                        "allowlisted_paths": item[paths_key],
                        "exclude": [
                            "code outside allowlisted documentation/docstrings",
                            "tests",
                            "generated documentation",
                            "binary assets",
                        ],
                    },
                    license_record=_repository_license(repository),
                )
            )
            ids.append(source_id)
        pairs.append(
            {
                "pair_id": f"ctu1_pair_api_{item['slug']}",
                "pair_type": "old_api_to_replacement_api",
                "left_source_id": ids[0],
                "right_source_id": ids[1],
                "left_condition": "deprecated_api",
                "right_condition": "replacement_api",
                "domain_group": "software_product_documentation",
                "domain_id": item["domain_id"],
                "planned_cases": 5,
                "authority_basis": (
                    "Both sides are immutable first-party documentation snapshots; "
                    "the project-authored deprecation notice identifies the replacement."
                ),
                "authority_scope": (
                    "Replacement status as documented by the first-party project "
                    "materials at the pinned revisions."
                ),
                "material_relationship_basis": item["relationship"],
                "relationship_evidence_urls": [item["evidence_url"]],
            }
        )
    return sources, pairs


def _olrc_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for title, item in sorted(OLRC_TITLES.items()):
        url = (
            "https://uscode.house.gov/download/releasepoints/us/pl/119/102/"
            f"xml_usc{title:02d}@119-102.zip"
        )
        sources.append(
            _base_source(
                source_id=f"temporal_olrc_title{title:02d}_119_102",
                condition="authoritative",
                source_family=f"temporal_olrc_title{title:02d}",
                domain_group="policy_regulatory",
                domain_id=f"federal_statutory_law_title{title:02d}",
                publication_window="2026",
                publisher="Office of the Law Revision Counsel, U.S. House",
                source_url=url,
                canonical_identifier=f"olrc:usc:title-{title}:release-point-119-102",
                acquisition_method="olrc_release_point_zip",
                immutable_revision={
                    "kind": "release_point",
                    "value": "119-102",
                    "release_date": "2026-07-12",
                    "expected_sha256": item["sha256"],
                    "expected_bytes": item["bytes"],
                },
                extraction={
                    "format": "USLM XML",
                    "section_selectors": item["selectors"],
                    "exclude": [
                        "editorial source-credit notes from question seed selection",
                        "third-party material",
                        "non-text assets",
                    ],
                },
                license_record=_government_license(),
            )
        )
    return sources


def _wikimedia_source(
    item: Mapping[str, Any],
    *,
    project: str,
    condition: str,
) -> dict[str, Any]:
    host = "en.wikisource.org" if project == "wikisource" else "en.wikipedia.org"
    title = str(item["title"])
    revision_id = int(item["revision_id"])
    return _base_source(
        source_id=f"temporal_{project}_{item['slug']}_r{revision_id}",
        condition=condition,
        source_family=f"temporal_{project}_{item['slug']}",
        domain_group="policy_regulatory",
        domain_id=str(item["domain_id"]),
        publication_window=str(item["revision_timestamp"])[:4],
        publisher="Wikimedia community",
        source_url=f"https://{host}/w/index.php?oldid={revision_id}",
        canonical_identifier=f"{project}:page-{item['page_id']}:revision-{revision_id}",
        acquisition_method="mediawiki_revision_api",
        immutable_revision={
            "kind": "mediawiki_revision",
            "value": revision_id,
            "page_id": item["page_id"],
            "revision_timestamp": item["revision_timestamp"],
            "reviewed_wikitext_bytes": item["length"],
        },
        extraction={
            "format": "wikitext",
            "page_title": title,
            "revision_id": revision_id,
            "exclude": [
                "references and external-link lists",
                "talk and user pages",
                "revision usernames and edit summaries",
                "templates unrelated to article text",
                "non-text media",
            ],
        },
        license_record=_wikimedia_license(),
    )


def _authority_pairs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = _olrc_sources()
    right_ids = {
        title: f"temporal_olrc_title{title:02d}_119_102" for title in OLRC_TITLES
    }
    pairs: list[dict[str, Any]] = []
    for item in WIKISOURCE_SOURCES:
        source = _wikimedia_source(item, project="wikisource", condition="noncanonical")
        sources.append(source)
        pairs.append(
            {
                "pair_id": f"ctu1_pair_noncanonical_{item['slug']}",
                "pair_type": "noncanonical_to_canonical",
                "left_source_id": source["source_id"],
                "right_source_id": right_ids[int(item["olrc_title"])],
                "left_condition": "noncanonical",
                "right_condition": "canonical",
                "domain_group": "policy_regulatory",
                "domain_id": item["domain_id"],
                "planned_cases": 5,
                "authority_basis": (
                    "The left side is a community-maintained Wikisource transcription; "
                    "the right side is the OLRC-prepared U.S. Code at release point "
                    "119-102, the official codification source for this contrast."
                ),
                "authority_scope": (
                    "Official-codification authority relative to a community copy; "
                    "positive-law status and any Statutes at Large caveat must be "
                    "preserved and ultimate legal effect is outside the task."
                ),
                "material_relationship_basis": (
                    f"Both sources identify {item['selector']}; acquisition must align "
                    "the selected statutory text and record any transcription/version "
                    "difference without editing either source."
                ),
                "relationship_evidence_urls": [
                    WIKIMEDIA_TERMS,
                    "https://uscode.house.gov/about_code.xhtml",
                    OLRC_DOWNLOADS,
                ],
            }
        )
    for item in WIKIPEDIA_SOURCES:
        source = _wikimedia_source(item, project="wikipedia", condition="low_authority")
        sources.append(source)
        pairs.append(
            {
                "pair_id": f"ctu1_pair_low_authority_{item['slug']}",
                "pair_type": "low_authority_to_authoritative",
                "left_source_id": source["source_id"],
                "right_source_id": right_ids[int(item["olrc_title"])],
                "left_condition": "low_authority",
                "right_condition": "authoritative",
                "domain_group": "policy_regulatory",
                "domain_id": item["domain_id"],
                "planned_cases": 5,
                "authority_basis": (
                    "Wikipedia is a community-authored informational summary and its "
                    "terms disclaim professional advice; OLRC prepares and publishes "
                    "the U.S. Code pursuant to federal law."
                ),
                "authority_scope": (
                    "Official-codification authority relative to a community "
                    "summary; positive-law status and any Statutes at Large caveat "
                    "must be preserved and ultimate legal effect is outside the task."
                ),
                "material_relationship_basis": (
                    f"The summary concerns {item['selector']}. Acquisition must retain "
                    "the revision verbatim and align only source metadata, never rewrite "
                    "the summary to match the statute."
                ),
                "relationship_evidence_urls": [
                    WIKIMEDIA_TERMS,
                    "https://uscode.house.gov/about_code.xhtml",
                    OLRC_DOWNLOADS,
                ],
            }
        )
    return sources, pairs


def _case_plan(pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    context_modes = (
        "left_only",
        "left_only",
        "mixed_left_first",
        "right_only",
        "mixed_right_first",
    )
    question_styles = (
        "direct_fact",
        "scope",
        "comparison",
        "constraints",
        "qualified_summary",
    )
    retrieval = ("bm25", "vector", "hybrid")
    cases: list[dict[str, Any]] = []
    global_index = 0
    for pair in sorted(pairs, key=lambda value: str(value["pair_id"])):
        short = str(pair["pair_id"]).removeprefix("ctu1_pair_")
        for slot in range(5):
            cases.append(
                {
                    "case_id": f"ctu1_temporal_{short}_{slot + 1:02d}",
                    "pair_id": pair["pair_id"],
                    "pair_type": pair["pair_type"],
                    "context_mode": context_modes[slot],
                    "question_style": question_styles[slot],
                    "retrieval_family": retrieval[global_index % len(retrieval)],
                    "chunk_size": 256 if global_index % 2 == 0 else 512,
                    "chunk_overlap": 32 if global_index % 2 == 0 else 64,
                    "reranking_enabled": global_index % 2 == 1,
                    "generator_route": "local" if global_index % 2 == 0 else "hosted",
                    "citation_format": ("source_id", "inline_numeric", "none")[
                        global_index % 3
                    ],
                }
            )
            global_index += 1
    return cases


def build_catalog() -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for builder in (_ecfr_sources, _api_sources, _authority_pairs):
        built_sources, built_pairs = builder()
        sources.extend(built_sources)
        pairs.extend(built_pairs)
    cases = _case_plan(pairs)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "created_at": "2026-07-26T00:00:00Z",
        "status": "locked_pending_owner_acquisition_authorization",
        "authorization": {
            "source_acquisition_authorized": False,
            "model_calls_authorized": False,
            "verifier_calls_authorized": False,
            "annotation_authorized": False,
            "external_exposure_attestation_complete": False,
            "required_next_decision": "approve_exact_temporal_source_acquisition",
        },
        "scope": {
            "planned_cases": 100,
            "planned_pairs": 20,
            "cases_per_pair": 5,
            "cases_per_pair_type": 25,
            "pair_types": list(PAIR_TYPES),
            "temporal_source_condition_only": True,
        },
        "acquisition_budget_usd": {
            "normal_operating_limit": 0.0,
            "hard_limit": 0.0,
            "paid_endpoints": 0,
        },
        "proposed_generation_budget_usd": {
            "scheduled_hosted_initial_requests": 50,
            "maximum_attempts_per_request": 2,
            "maximum_request_input_utf8_bytes": 50000,
            "maximum_output_tokens_per_attempt": 800,
            "conservative_all_attempts_upper_bound": 1.41,
            "normal_operating_limit": 2.0,
            "hard_limit": 3.0,
            "generation_not_yet_authorized": True,
        },
        "source_review": {
            "government_terms_url": GOVINFO_TERMS,
            "wikimedia_terms_url": WIKIMEDIA_TERMS,
            "ecfr_api_documentation_url": ECFR_API_DOCS,
            "olrc_downloads_url": OLRC_DOWNLOADS,
            "reviewed_at": "2026-07-26",
            "reviewed_by": "Codex-assisted machine review; owner approval pending",
        },
        "sources": sorted(sources, key=lambda value: str(value["source_id"])),
        "pairs": sorted(pairs, key=lambda value: str(value["pair_id"])),
        "case_plan": sorted(cases, key=lambda value: str(value["case_id"])),
    }


def validate_catalog(
    catalog: Mapping[str, Any],
    *,
    calibration_registry: Mapping[str, Any] | None = None,
    natural_source_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise TemporalCatalogError("Unexpected schema version.")
    if catalog.get("record_kind") != RECORD_KIND:
        raise TemporalCatalogError("Unexpected record kind.")
    if catalog.get("status") != "locked_pending_owner_acquisition_authorization":
        raise TemporalCatalogError("Catalog is not at the pre-acquisition lock.")
    authorization = catalog.get("authorization") or {}
    if any(
        authorization.get(field)
        for field in (
            "source_acquisition_authorized",
            "model_calls_authorized",
            "verifier_calls_authorized",
            "annotation_authorized",
            "external_exposure_attestation_complete",
        )
    ):
        raise TemporalCatalogError("Pre-acquisition catalog cannot grant authorization.")

    sources = catalog.get("sources")
    pairs = catalog.get("pairs")
    cases = catalog.get("case_plan")
    if not isinstance(sources, list) or not isinstance(pairs, list) or not isinstance(
        cases, list
    ):
        raise TemporalCatalogError("Sources, pairs, and case_plan must be arrays.")
    source_ids = [str(source.get("source_id") or "") for source in sources]
    pair_ids = [str(pair.get("pair_id") or "") for pair in pairs]
    case_ids = [str(case.get("case_id") or "") for case in cases]
    for label, values in (
        ("source", source_ids),
        ("pair", pair_ids),
        ("case", case_ids),
    ):
        if not all(values) or len(values) != len(set(values)):
            raise TemporalCatalogError(f"{label} IDs are missing or duplicated.")
    if len(pairs) != 20 or len(cases) != 100:
        raise TemporalCatalogError("Temporal lock requires 20 pairs and 100 cases.")

    indexed_sources = {
        str(source["source_id"]): source for source in sources
    }
    indexed_pairs = {str(pair["pair_id"]): pair for pair in pairs}
    pair_type_counts = Counter(str(pair["pair_type"]) for pair in pairs)
    if pair_type_counts != Counter({pair_type: 5 for pair_type in PAIR_TYPES}):
        raise TemporalCatalogError("Pair types are not balanced at five pairs each.")
    case_pair_type_counts = Counter(str(case["pair_type"]) for case in cases)
    if case_pair_type_counts != Counter({pair_type: 25 for pair_type in PAIR_TYPES}):
        raise TemporalCatalogError("Case plan is not balanced at 25 cases per type.")

    for source in sources:
        source_id = str(source["source_id"])
        if source["domain_group"] not in {
            "policy_regulatory",
            "software_product_documentation",
        }:
            raise TemporalCatalogError(f"Unexpected domain group for {source_id}.")
        if source["access"] != _access():
            raise TemporalCatalogError(f"Access/privacy lock changed for {source_id}.")
        if source["license"]["review_status"] != (
            "machine_review_passed_owner_pending"
        ):
            raise TemporalCatalogError(f"License review state changed for {source_id}.")
        revision = source.get("immutable_revision") or {}
        kind = revision.get("kind")
        value = revision.get("value")
        if kind == "git_commit" and not re.fullmatch(r"[a-f0-9]{40}", str(value)):
            raise TemporalCatalogError(f"Invalid git commit for {source_id}.")
        if kind == "mediawiki_revision" and (
            not isinstance(value, int) or value < 1
        ):
            raise TemporalCatalogError(f"Invalid MediaWiki revision for {source_id}.")
        if kind in {"effective_date", "release_point"}:
            expected = str(revision.get("expected_sha256") or "")
            if not re.fullmatch(r"[a-f0-9]{64}", expected):
                raise TemporalCatalogError(f"Missing expected hash for {source_id}.")
        if kind not in {
            "git_commit",
            "mediawiki_revision",
            "effective_date",
            "release_point",
        }:
            raise TemporalCatalogError(f"Unsupported immutability kind for {source_id}.")

    for pair in pairs:
        pair_id = str(pair["pair_id"])
        pair_type = str(pair["pair_type"])
        left_id = str(pair["left_source_id"])
        right_id = str(pair["right_source_id"])
        if left_id == right_id or left_id not in indexed_sources or right_id not in indexed_sources:
            raise TemporalCatalogError(f"Invalid source references for {pair_id}.")
        expected_conditions = PAIR_TYPE_CONDITIONS[pair_type]
        actual_conditions = (
            pair.get("left_condition"),
            pair.get("right_condition"),
        )
        if actual_conditions != expected_conditions:
            raise TemporalCatalogError(f"Pair conditions changed for {pair_id}.")
        if indexed_sources[left_id]["condition"] != actual_conditions[0]:
            raise TemporalCatalogError(f"Left source condition changed for {pair_id}.")
        right_source_condition = indexed_sources[right_id]["condition"]
        permitted_right_source_conditions = {
            "current": {"current"},
            "replacement_api": {"replacement_api"},
            "canonical": {"canonical", "authoritative"},
            "authoritative": {"authoritative"},
        }[str(actual_conditions[1])]
        if right_source_condition not in permitted_right_source_conditions:
            raise TemporalCatalogError(f"Right source condition changed for {pair_id}.")
        if int(pair.get("planned_cases", 0)) != 5:
            raise TemporalCatalogError(f"Pair allocation changed for {pair_id}.")
        if (
            not pair.get("authority_basis")
            or not pair.get("authority_scope")
            or not pair.get("material_relationship_basis")
        ):
            raise TemporalCatalogError(f"Pair evidence is incomplete for {pair_id}.")
        evidence = pair.get("relationship_evidence_urls")
        if not isinstance(evidence, list) or not evidence:
            raise TemporalCatalogError(f"Pair evidence URLs are absent for {pair_id}.")

    for case in cases:
        pair = indexed_pairs.get(str(case["pair_id"]))
        if pair is None or case["pair_type"] != pair["pair_type"]:
            raise TemporalCatalogError(f"Case pair mapping changed for {case['case_id']}.")
    if Counter(str(case["generator_route"]) for case in cases) != Counter(
        {"local": 50, "hosted": 50}
    ):
        raise TemporalCatalogError("Generator route allocation is not 50/50.")
    retrieval_counts = Counter(str(case["retrieval_family"]) for case in cases)
    if retrieval_counts != Counter({"bm25": 34, "vector": 33, "hybrid": 33}):
        raise TemporalCatalogError("Retrieval allocation changed.")
    context_counts = Counter(str(case["context_mode"]) for case in cases)
    if context_counts != Counter(
        {
            "left_only": 40,
            "mixed_left_first": 20,
            "right_only": 20,
            "mixed_right_first": 20,
        }
    ):
        raise TemporalCatalogError("Source-condition context allocation changed.")

    candidate_families = {str(source["source_family"]) for source in sources}
    candidate_domains = {str(source["domain_id"]) for source in sources}
    candidate_identifiers = {
        str(source["canonical_identifier"]) for source in sources
    }
    overlaps: dict[str, list[str]] = {}
    for label, manifest in (
        ("calibration", calibration_registry),
        ("natural", natural_source_manifest),
    ):
        if manifest is None:
            continue
        prior_sources = manifest.get("sources") or []
        family_overlap = sorted(
            candidate_families
            & {str(source.get("source_family")) for source in prior_sources}
        )
        domain_overlap = sorted(
            candidate_domains & {str(source.get("domain_id")) for source in prior_sources}
        )
        identifier_overlap = sorted(
            candidate_identifiers
            & {str(source.get("canonical_identifier")) for source in prior_sources}
        )
        if family_overlap or domain_overlap or identifier_overlap:
            overlaps[label] = family_overlap + domain_overlap + identifier_overlap
    if overlaps:
        raise TemporalCatalogError(
            f"Temporal source identities overlap prior corpora: {canonical_json(overlaps)}"
        )

    budget = catalog["proposed_generation_budget_usd"]
    if float(budget["conservative_all_attempts_upper_bound"]) > float(
        budget["hard_limit"]
    ):
        raise TemporalCatalogError("Proposed generation upper bound exceeds hard limit.")
    if catalog["acquisition_budget_usd"] != {
        "normal_operating_limit": 0.0,
        "hard_limit": 0.0,
        "paid_endpoints": 0,
    }:
        raise TemporalCatalogError("Source acquisition must remain zero-cost.")
    return {
        "status": "valid_pending_owner_authorization",
        "source_count": len(sources),
        "pair_count": len(pairs),
        "case_count": len(cases),
        "pair_type_counts": dict(sorted(pair_type_counts.items())),
        "case_pair_type_counts": dict(sorted(case_pair_type_counts.items())),
        "retrieval_counts": dict(sorted(retrieval_counts.items())),
        "context_mode_counts": dict(sorted(context_counts.items())),
        "generator_route_counts": dict(
            sorted(Counter(str(case["generator_route"]) for case in cases).items())
        ),
        "acquisition_hard_limit_usd": 0.0,
        "proposed_generation_hard_limit_usd": float(budget["hard_limit"]),
        "model_calls_authorized": False,
        "verifier_calls_authorized": False,
        "labels_accessible": False,
    }


def build_command(output: Path) -> dict[str, Any]:
    catalog = build_catalog()
    encoded = (
        json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if output.exists() and output.read_bytes() != encoded:
        raise TemporalCatalogError(
            f"Refusing to overwrite a different temporal catalog: {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return {"catalog_sha256": digest, "catalog": catalog}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/"
            "temporal_pre_acquisition_catalog.json"
        ),
    )
    parser.add_argument(
        "--calibration-registry",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/calibration/registry.json"),
    )
    parser.add_argument(
        "--natural-source-manifest",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"
        ),
    )
    args = parser.parse_args(argv)
    built = build_command(args.output)
    calibration = json.loads(args.calibration_registry.read_text(encoding="utf-8"))
    natural = json.loads(args.natural_source_manifest.read_text(encoding="utf-8"))
    result = validate_catalog(
        built["catalog"],
        calibration_registry=calibration,
        natural_source_manifest=natural,
    )
    print(
        json.dumps(
            {"catalog_sha256": built["catalog_sha256"], **result},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
