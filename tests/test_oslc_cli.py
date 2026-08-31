from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main
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


def test_oslc_cli_rejects_unknown_action(tmp_path: Path, capsys) -> None:
    assert main(["--root", str(tmp_path), "oslc", "write"]) == 2
    assert "Unknown OSLC action: write" in capsys.readouterr().err
