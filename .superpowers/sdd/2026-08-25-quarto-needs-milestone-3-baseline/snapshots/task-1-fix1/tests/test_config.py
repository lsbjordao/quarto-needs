from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quarto_needs.config import (
    ConfigurationError,
    Gates,
    NeedsConfig,
    RelationPolicy,
    RuleSetting,
    reference_date,
)


def test_missing_file_yields_embedded_defaults(tmp_path: Path) -> None:
    config = load = __import__("quarto_needs.config", fromlist=["load_config"]).load_config(tmp_path)
    assert isinstance(config, NeedsConfig)
    assert config.profile == "default"
    assert config.rule_settings == {}
    assert config.named_query_sources == {}
    assert config.relation_policies == {}
    assert config.required_attributes == {}
    assert config.test_types == ("test-case",)
    assert config.risk_types == ("risk",)
    assert config.successful_test_statuses == ("passed",)
    assert config.ineffective_endpoint_statuses == ("disapproved", "rejected", "failed", "deprecated")
    assert config.expiry_attribute == "expires"
    assert config.gates == Gates()


def test_full_document_parses_every_section(tmp_path: Path) -> None:
    source = tmp_path / ".quarto-needs.toml"
    source.write_text(
        'profile = "strict"\n'
        "[types.functional-requirement]\n"
        'required-attributes = ["priority"]\n'
        '[relations."verified-by"]\n'
        'allowed-source-types = ["functional-requirement"]\n'
        "minimum-per-source = 1\n"
        "[governance]\n"
        'test-types = ["test-case"]\n'
        'risk-types = ["risk"]\n'
        'successful-test-statuses = ["passed"]\n'
        'expiry-attribute = "valid-until"\n'
        '[rules.REQ006]\nseverity = "error"\n'
        '[rules.REQ014]\nenabled = false\n'
        "[queries.approved-high-unverified]\n"
        'all = [{ field = "status", op = "eq", value = "approved" }]\n'
        '[gates]\nmax-errors = 0\n'
        "min-evidence = 90.5\n",
        encoding="utf-8",
    )
    from quarto_needs.config import load_config

    config = load_config(tmp_path)
    assert config.profile == "strict"
    assert config.required_attributes["functional-requirement"] == ("priority",)
    assert config.relation_policies["verified-by"].minimum_per_source == 1
    assert config.relation_policies["verified-by"].allowed_source_types == ("functional-requirement",)
    assert config.test_types == ("test-case",)
    assert config.risk_types == ("risk",)
    assert config.successful_test_statuses == ("passed",)
    assert config.expiry_attribute == "valid-until"
    assert config.rule_settings["REQ006"] == RuleSetting(enabled=True, severity="error")
    assert config.rule_settings["REQ014"] == RuleSetting(enabled=False, severity=None)
    assert "approved-high-unverified" in config.named_query_sources
    assert config.gates.max_errors == 0
    assert config.gates.min_evidence == 90.5


def test_unknown_top_level_key_is_a_configuration_error(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text('profle = "strict"\n', encoding="utf-8")
    from quarto_needs.config import load_config

    with pytest.raises(ConfigurationError, match="profle"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "document",
    [
        'profile = "pedantic"\n',
        '[rules.REQ999]\nenabled = true\n',
        '[rules.REQ002]\nseverity = "fatal"\n',
        '[relations."verified-by"]\nminimum-per-source = -1\n',
        "[gates]\nmin-evidence = 150\n",
        '[types.""]\nrequired-attributes = ["x"]\n',
    ],
)
def test_invalid_values_are_configuration_errors(tmp_path: Path, document: str) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(document, encoding="utf-8")
    from quarto_needs.config import load_config

    with pytest.raises(ConfigurationError):
        load_config(tmp_path)


def test_malformed_toml_is_a_configuration_error(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text("not [ valid tomld", encoding="utf-8")
    from quarto_needs.config import load_config

    with pytest.raises(ConfigurationError):
        load_config(tmp_path)


def test_reference_date_prefers_source_date_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1704067200")
    assert reference_date() == date(2024, 1, 1)


def test_reference_date_falls_back_to_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert reference_date() == date.today()


def test_config_is_immutable(tmp_path: Path) -> None:
    from quarto_needs.config import load_config

    config = load_config(tmp_path)
    with pytest.raises(Exception):
        config.profile = "strict"  # type: ignore[misc]
