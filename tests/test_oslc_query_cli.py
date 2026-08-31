from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main
from quarto_needs.oslc_cli import discovery_to_dict
from quarto_needs.oslc_federation import DiscoveredResourceShape, OslcDiscoveryResult
from quarto_needs.oslc_query import OslcQueryMember, OslcQueryResult, RDFS_MEMBER
from quarto_needs.oslc_rm import OslcQueryCapability, OslcRmService
from quarto_needs.oslc_shape import OslcResourceShape, OslcShapeProperty


def test_oslc_query_cli_uses_named_project_profile_and_does_not_leak_secret(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        """
[federation.oslc.profiles.production]
service-provider-uri = "https://provider.test/oslc/sp/1"
cache-dir = ".quarto-needs/oslc/production"
max-age-seconds = 900
allow-stale = true
timeout-seconds = 3.5
max-bytes = 250000
max-redirects = 1
max-nodes = 700
bearer-token-env = "QUARTO_NEEDS_OSLC_TOKEN"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("QUARTO_NEEDS_OSLC_TOKEN", "query-secret")
    captured = {}

    def fake_query(**kwargs):
        captured.update(kwargs)
        return OslcQueryResult(
            query_base_uri="https://provider.test/oslc/rm/requirements",
            fetch_source="live",
            response_digest="sha256:" + "2" * 64,
            fetched_at="2026-08-30T21:00:00Z",
            member_property_uri=RDFS_MEMBER,
            members=(
                OslcQueryMember(
                    resource_uri="https://provider.test/oslc/rm/requirements/1"
                ),
            ),
        )

    monkeypatch.setattr("quarto_needs.oslc_cli.execute_oslc_query", fake_query)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "query",
                "https://provider.test/oslc/rm/requirements",
                "--profile",
                "production",
                "--max-members",
                "25",
                "--format",
                "json",
            ]
        )
        == 0
    )

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["schema"] == "oslc-query-result-v1"
    assert payload["members"][0]["resourceUri"].endswith("/1")
    assert "query-secret" not in output.out
    assert "query-secret" not in output.err
    assert captured["service_provider_uri"] == "https://provider.test/oslc/sp/1"
    assert captured["cache_root"] == tmp_path / ".quarto-needs" / "oslc" / "production"
    assert captured["cache_policy"].max_age_seconds == 900
    assert captured["cache_policy"].allow_stale is True
    assert captured["fetch_policy"].timeout_seconds == 3.5
    assert captured["fetch_policy"].max_bytes == 250000
    assert captured["fetch_policy"].max_redirects == 1
    assert captured["max_nodes"] == 700
    assert captured["max_members"] == 25
    assert captured["auth_headers"] == {"Authorization": "Bearer query-secret"}


def test_oslc_query_cli_requires_explicit_provider_identity(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "query",
                "https://provider.test/oslc/rm/requirements",
            ]
        )
        == 2
    )
    assert "--service-provider-uri or --profile is required" in capsys.readouterr().err


def test_discovery_json_serializes_resource_shape_value_shapes() -> None:
    shape = OslcResourceShape(
        shape_uri="https://provider.test/oslc/shapes/query",
        describes=("http://open-services.net/ns/rm#Requirement",),
        properties=(
            OslcShapeProperty(
                name="member",
                property_definition=RDFS_MEMBER,
                occurs="http://open-services.net/ns/core#Zero-or-many",
                value_shapes=("https://provider.test/oslc/shapes/requirement",),
            ),
        ),
    )
    result = OslcDiscoveryResult(
        service_provider_uri="https://provider.test/oslc/sp/1",
        provider_fetch_source="live",
        services=(
            OslcRmService(
                service_id="https://provider.test/oslc/service/rm",
                query_capabilities=(
                    OslcQueryCapability(
                        query_base_uri="https://provider.test/oslc/rm/requirements",
                        resource_shape_uri=shape.shape_uri,
                    ),
                ),
            ),
        ),
        resource_shapes=(
            DiscoveredResourceShape(uri=shape.shape_uri, fetch_source="live", shape=shape),
        ),
    )

    payload = discovery_to_dict(result)
    prop = payload["resourceShapes"][0]["properties"][0]
    assert prop["valueShapes"] == ["https://provider.test/oslc/shapes/requirement"]
