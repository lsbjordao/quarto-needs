from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.oslc_rm import (
    DCTERMS_NS,
    OSLC_CORE_NS,
    OSLC_REQUIREMENT,
    OSLC_RM_NS,
    QN_OSLC_NS,
    ExternalResourceIdentity,
    build_requirement_resources,
    content_digest,
    resource_uri,
)


def _write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #SYS-001 type=system-requirement status=approved implemented-by=COMP-001 verified-by=TC-001 depends-on=SYS-002}\n"
        "## Authenticate users\n"
        "The system shall authenticate users.\n"
        ":::\n\n"
        "::: {.need #SYS-002 type=system-requirement status=approved}\n"
        "## Keep audit records\n"
        "The system shall retain audit records.\n"
        ":::\n\n"
        "::: {.need #COMP-001 type=component status=implemented}\n"
        "## Auth service\n"
        "Implements authentication.\n"
        ":::\n\n"
        "::: {.need #TC-001 type=test-case status=passed}\n"
        "## Authentication test\n"
        "Verify login.\n"
        ":::\n",
        encoding="utf-8",
    )


def _snapshot(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def test_oslc_projection_exports_only_requirement_resources(tmp_path: Path) -> None:
    _write_project(tmp_path)
    resources = build_requirement_resources(
        _snapshot(tmp_path),
        base_uri="https://example.test/oslc/rm",
        service_provider_uri="https://example.test/oslc/service-provider/1",
    )

    assert [item[f"{DCTERMS_NS}identifier"] for item in resources] == [
        "SYS-001",
        "SYS-002",
    ]
    assert all(item["@type"] == OSLC_REQUIREMENT for item in resources)
    assert all(
        item[f"{OSLC_CORE_NS}serviceProvider"]["@id"]
        == "https://example.test/oslc/service-provider/1"
        for item in resources
    )


def test_oslc_projection_maps_only_conservative_rm_relations(tmp_path: Path) -> None:
    _write_project(tmp_path)
    resources = build_requirement_resources(
        _snapshot(tmp_path),
        base_uri="https://example.test/oslc/rm",
        service_provider_uri="https://example.test/oslc/service-provider/1",
    )
    requirement = next(
        item for item in resources if item[f"{DCTERMS_NS}identifier"] == "SYS-001"
    )

    assert requirement[f"{OSLC_RM_NS}implementedBy"] == [
        {"@id": "https://example.test/oslc/rm/resource/COMP-001"}
    ]
    assert requirement[f"{OSLC_RM_NS}validatedBy"] == [
        {"@id": "https://example.test/oslc/rm/resource/TC-001"}
    ]
    assert f"{OSLC_RM_NS}dependsOn" not in requirement

    relations = requirement[f"{QN_OSLC_NS}relations"]
    canonical_names = {relation["canonicalRelation"] for relation in relations}
    assert canonical_names == {"depends-on", "implemented-by", "verified-by"}
    depends_on = next(
        relation for relation in relations if relation["canonicalRelation"] == "depends-on"
    )
    assert "oslcProperty" not in depends_on


def test_oslc_resource_uri_requires_http_and_encodes_canonical_id() -> None:
    assert (
        resource_uri("https://example.test/oslc", "REQ 1/α")
        == "https://example.test/oslc/resource/REQ%201%2F%CE%B1"
    )
    with pytest.raises(ValueError, match="absolute http"):
        resource_uri("urn:local", "REQ-1")


def test_external_resource_identity_requires_provenance_digest_and_http_uris() -> None:
    digest = content_digest(b"payload")
    identity = ExternalResourceIdentity(
        resource_uri="https://provider.test/requirements/1",
        service_provider_uri="https://provider.test/oslc/sp/1",
        digest=digest,
        fetched_at="2026-08-30T21:00:00Z",
        trust_state="trusted",
        etag='"abc"',
    )
    assert identity.digest == digest
    assert identity.trust_state == "trusted"

    with pytest.raises(ValueError, match="sha256"):
        ExternalResourceIdentity(
            resource_uri="https://provider.test/requirements/1",
            service_provider_uri="https://provider.test/oslc/sp/1",
            digest="md5:bad",
            fetched_at="2026-08-30T21:00:00Z",
        )
