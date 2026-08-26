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
    embedded_defaults,
    load_config,
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


def test_canonical_document_is_order_independent(tmp_path: Path) -> None:
    """Two spellings of the same policy must canonicalize identically."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n',
        encoding="utf-8",
    )
    (second / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n',
        encoding="utf-8",
    )

    assert load_config(first).canonical_document() == load_config(second).canonical_document()


def test_canonical_document_excludes_presence_and_path(tmp_path: Path) -> None:
    """Presence controls artifact projection, not graph semantics."""
    (tmp_path / ".quarto-needs.toml").write_text("", encoding="utf-8")

    from_file = load_config(tmp_path).canonical_document()
    embedded = embedded_defaults().canonical_document()

    assert from_file == embedded
    assert "present" not in from_file
    assert not any("quarto-needs.toml" in str(value) for value in from_file.values())


def test_canonical_document_reflects_every_policy_section(tmp_path: Path) -> None:
    """A change in any supported section must change the canonical document."""
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "advisory"\n'
        '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
        '[governance]\ntest-types = ["test-case"]\n'
        '[rules.REQ011]\nenabled = true\n'
        '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
        '[gates]\nmax-errors = 3\n',
        encoding="utf-8",
    )

    document = load_config(tmp_path).canonical_document()

    assert document["profile"] == "advisory"
    assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
    assert document["governance"]["test-types"] == ["test-case"]
    assert document["rules"]["REQ011"]["enabled"] is True
    assert "q" in document["queries"]
    assert document["gates"]["max-errors"] == 3
