from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main
from quarto_needs.oslc_catalog import OslcCatalogResult
from quarto_needs.oslc_federation import OslcDiscoveryResult
from quarto_needs.oslc_rm import OslcQueryCapability, OslcRmService


def _result() -> OslcDiscoveryResult:
    return OslcDiscoveryResult(
        service_provider_uri="https://provider.test/oslc/sp/1",
        provider_fetch_source="live",
        services=(
            OslcRmService(
                service_id="https://provider.test/oslc/service/rm",
                query_capabilities=(
                    OslcQueryCapability(
                        query_base_uri="https://provider.test/oslc/rm/requirements",
                        resource_shape_uri=None,
                        resource_types=("http://open-services.net/ns/rm#Requirement",),
                    ),
                ),
            ),
        ),
        resource_shapes=(),
    )


def test_installed_cli_discovers_oslc_as_deterministic_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    captured = {}

    def fake_discover(**kwargs):
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr("quarto_needs.oslc_cli.discover_oslc_rm", fake_discover)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "oslc",
            "discover",
            "https://provider.test/oslc/sp/1",
            "--format",
            "json",
            "--now",
            "2026-08-30T21:00:00Z",
            "--max-age-seconds",
            "7200",
            "--max-bytes",
            "4096",
            "--max-nodes",
            "200",
            "--no-shapes",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "providerFetchSource": "live",
        "resourceShapes": [],
        "schema": "oslc-discovery-v1",
        "serviceProviderUri": "https://provider.test/oslc/sp/1",
        "services": [
            {
                "queryCapabilities": [
                    {
                        "queryBaseUri": "https://provider.test/oslc/rm/requirements",
                        "resourceShapeUri": None,
                        "resourceTypes": ["http://open-services.net/ns/rm#Requirement"],
                    }
                ],
                "serviceId": "https://provider.test/oslc/service/rm",
            }
        ],
    }
    assert captured["service_provider_uri"] == "https://provider.test/oslc/sp/1"
    assert captured["cache_root"] == tmp_path / ".quarto-needs" / "oslc-cache"
    assert captured["cache_policy"].max_age_seconds == 7200
    assert captured["fetch_policy"].max_bytes == 4096
    assert captured["max_nodes"] == 200
    assert captured["fetch_shapes"] is False


def test_oslc_cli_reads_named_profile_and_allows_explicit_override(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / ".quarto-needs-oslc.toml").write_text(
        """
[profiles.production]
service-provider-uri = "https://provider.test/oslc/sp/1"
cache-dir = ".quarto-needs/oslc/production"
max-age-seconds = 900
allow-stale = true
timeout-seconds = 3.5
max-bytes = 250000
max-redirects = 1
max-nodes = 700
fetch-shapes = false
bearer-token-env = "QUARTO_NEEDS_OSLC_TOKEN"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("QUARTO_NEEDS_OSLC_TOKEN", "profile-secret")
    captured = {}

    def fake_discover(**kwargs):
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr("quarto_needs.oslc_cli.discover_oslc_rm", fake_discover)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "discover",
                "--profile",
                "production",
                "--max-bytes",
                "4096",
                "--shapes",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert "profile-secret" not in output.out
    assert "profile-secret" not in output.err
    assert captured["service_provider_uri"] == "https://provider.test/oslc/sp/1"
    assert captured["cache_root"] == tmp_path / ".quarto-needs" / "oslc" / "production"
    assert captured["cache_policy"].max_age_seconds == 900
    assert captured["cache_policy"].allow_stale is True
    assert captured["fetch_policy"].timeout_seconds == 3.5
    assert captured["fetch_policy"].max_bytes == 4096
    assert captured["fetch_policy"].max_redirects == 1
    assert captured["max_nodes"] == 700
    assert captured["fetch_shapes"] is True
    assert captured["auth_headers"] == {"Authorization": "Bearer profile-secret"}


def test_oslc_cli_catalog_reports_one_level_without_recursive_follow(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    captured = {}

    def fake_catalog(**kwargs):
        captured.update(kwargs)
        return OslcCatalogResult(
            catalog_uri="https://provider.test/oslc/catalog",
            fetch_source="live",
            service_provider_uris=(
                "https://provider.test/oslc/sp/a",
                "https://provider.test/oslc/sp/b",
            ),
            nested_catalog_uris=("https://provider.test/oslc/catalog/nested",),
        )

    monkeypatch.setattr("quarto_needs.oslc_cli.discover_oslc_catalog", fake_catalog)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "catalog",
                "https://provider.test/oslc/catalog",
                "--format",
                "json",
                "--max-providers",
                "10",
                "--max-nested-catalogs",
                "2",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "catalogUri": "https://provider.test/oslc/catalog",
        "fetchSource": "live",
        "nestedCatalogUris": ["https://provider.test/oslc/catalog/nested"],
        "schema": "oslc-catalog-v1",
        "serviceProviderUris": [
            "https://provider.test/oslc/sp/a",
            "https://provider.test/oslc/sp/b",
        ],
    }
    assert captured["max_providers"] == 10
    assert captured["max_nested_catalogs"] == 2


def test_oslc_cli_reads_bearer_token_from_environment_without_printing_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    secret = "token-that-must-not-leak"
    monkeypatch.setenv("QUARTO_NEEDS_OSLC_TOKEN", secret)
    captured = {}

    def fake_discover(**kwargs):
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr("quarto_needs.oslc_cli.discover_oslc_rm", fake_discover)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "discover",
                "https://provider.test/oslc/sp/1",
                "--bearer-token-env",
                "QUARTO_NEEDS_OSLC_TOKEN",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert captured["auth_headers"] == {"Authorization": f"Bearer {secret}"}
    assert secret not in output.out
    assert secret not in output.err


def test_oslc_cli_rejects_missing_secret_environment_variable(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("MISSING_OSLC_TOKEN", raising=False)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "discover",
                "https://provider.test/oslc/sp/1",
                "--bearer-token-env",
                "MISSING_OSLC_TOKEN",
            ]
        )
        == 2
    )
    assert "unset or empty" in capsys.readouterr().err


def test_oslc_cli_rejects_profile_and_uri_together(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "oslc",
                "discover",
                "https://provider.test/oslc/sp/1",
                "--profile",
                "production",
            ]
        )
        == 2
    )
    assert "either a Service Provider URI or --profile" in capsys.readouterr().err


def test_oslc_cli_rejects_unknown_action(tmp_path: Path, capsys) -> None:
    assert main(["--root", str(tmp_path), "oslc", "write"]) == 2
    assert "Unknown OSLC action: write" in capsys.readouterr().err
