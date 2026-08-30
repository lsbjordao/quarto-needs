from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.fingerprints import configuration_fingerprint
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def _write_project(tmp_path: Path, priority: str = "high", budget: str = "250") -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.non-functional-requirement]
id-prefix = "NFR-"
role = "requirement"
allowed-statuses = ["approved"]

[types.non-functional-requirement.attribute-schema]
type = "object"
required = ["priority", "budget-ms"]

[types.non-functional-requirement.attribute-schema.properties.priority]
enum = ["critical", "high"]

[types.non-functional-requirement.attribute-schema.properties.budget-ms]
type = "string"
pattern = "^[1-9][0-9]{0,2}$"
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.qmd").write_text(
        f'''::: {{.need #NFR-001 type="non-functional-requirement" status="approved" priority="{priority}" budget-ms="{budget}"}}
## Latency budget
Body.
:::
''',
        encoding="utf-8",
    )


def test_attribute_schema_is_canonical_and_validates_object_attributes(tmp_path: Path) -> None:
    _write_project(tmp_path)
    config = load_config(tmp_path)
    canonical = config.canonical_document()
    schema = canonical["types"]["non-functional-requirement"]["attribute-schema"]
    assert schema["type"] == "object"
    assert schema["properties"]["priority"]["enum"] == ["critical", "high"]
    assert schema["properties"]["budget-ms"]["type"] == "string"

    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    assert not [finding for finding in result.snapshot.findings if finding.code == "OBJ002"]


def test_attribute_schema_violation_is_deterministic_obj002_finding(tmp_path: Path) -> None:
    _write_project(tmp_path, priority="medium")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    findings = [finding for finding in result.snapshot.findings if finding.code == "OBJ002"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.object_id == "NFR-001"
    assert finding.severity == "error"
    assert finding.properties["type"] == "non-functional-requirement"
    assert finding.properties["instancePath"] == "/priority"
    assert finding.properties["validator"] == "enum"


def test_attribute_schema_can_validate_string_shape_without_coercion(tmp_path: Path) -> None:
    _write_project(tmp_path, budget="1000")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    finding = next(finding for finding in result.snapshot.findings if finding.code == "OBJ002")
    assert finding.properties["instancePath"] == "/budget-ms"
    assert finding.properties["validator"] == "pattern"


def test_attribute_schema_severity_can_be_overridden_by_rule_setting(tmp_path: Path) -> None:
    _write_project(tmp_path, priority="medium")
    path = tmp_path / ".quarto-needs.toml"
    path.write_text(
        path.read_text(encoding="utf-8") + '\n[rules.OBJ002]\nseverity = "warning"\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    finding = next(finding for finding in result.snapshot.findings if finding.code == "OBJ002")
    assert finding.severity == "warning"


def test_remote_schema_reference_is_rejected_at_config_load(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement.attribute-schema]
"$ref" = "https://example.invalid/schema.json"
''',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="must be local"):
        load_config(tmp_path)


def test_local_schema_reference_is_allowed(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement.attribute-schema]
"$ref" = "#/$defs/attrs"

[types.functional-requirement.attribute-schema."$defs".attrs]
type = "object"

[types.functional-requirement.attribute-schema."$defs".attrs.properties.priority]
type = "string"
''',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.attribute_schemas["functional-requirement"]["$ref"] == "#/$defs/attrs"


def test_invalid_json_schema_is_configuration_error(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement.attribute-schema]
type = 7
''',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Draft 2020-12"):
        load_config(tmp_path)


def test_attribute_schema_change_changes_configuration_fingerprint(tmp_path: Path) -> None:
    _write_project(tmp_path)
    first = load_config(tmp_path)
    first_fingerprint = configuration_fingerprint(
        first, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    path = tmp_path / ".quarto-needs.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'pattern = "^[1-9][0-9]{0,2}$"',
            'pattern = "^[1-9][0-9]{0,1}$"',
        ),
        encoding="utf-8",
    )
    second = load_config(tmp_path)
    second_fingerprint = configuration_fingerprint(
        second, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    assert first_fingerprint != second_fingerprint
