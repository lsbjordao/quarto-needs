from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.fingerprints import configuration_fingerprint
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def _write_project(tmp_path: Path, *, with_evidence: bool) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"
[types.test-case]
role = "verification"
[types.evidence]
role = "evidence"

[queries.approved-functional]
all = [
  { field = "type", op = "eq", value = "functional-requirement" },
  { field = "status", op = "eq", value = "approved" },
]

[constraints.REQUIRE_EXECUTABLE_PROOF]
kind = "required-path"
scope = "approved-functional"
relations = ["verified-by", "evidenced-by"]
target-role = "evidence"
severity = "error"
''',
        encoding="utf-8",
    )
    evidence_relation = ' evidenced-by="EVD-1"' if with_evidence else ""
    evidence_object = '''
::: {.need #EVD-1 type="evidence" status="verified"}
## Evidence
:::
''' if with_evidence else ""
    (tmp_path / "model.qmd").write_text(
        f'''::: {{.need #FUN-1 type="functional-requirement" status="approved" verified-by="TC-1"}}
## Requirement
:::
::: {{.need #TC-1 type="test-case" status="passed"{evidence_relation}}}
## Test
:::
{evidence_object}''',
        encoding="utf-8",
    )


def test_configured_constraint_is_canonical_and_emits_finding(tmp_path: Path) -> None:
    _write_project(tmp_path, with_evidence=False)
    config = load_config(tmp_path)
    assert config.canonical_document()["constraints"] == {
        "REQUIRE_EXECUTABLE_PROOF": {
            "kind": "required-path",
            "scope": "approved-functional",
            "relations": ["verified-by", "evidenced-by"],
            "target-role": "evidence",
            "severity": "error",
        }
    }
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    findings = [
        finding for finding in result.snapshot.findings
        if finding.code == "CONSTRAINT:REQUIRE_EXECUTABLE_PROOF"
    ]
    assert [(finding.object_id, finding.severity) for finding in findings] == [
        ("FUN-1", "error")
    ]


def test_configured_constraint_passes_when_required_path_exists(tmp_path: Path) -> None:
    _write_project(tmp_path, with_evidence=True)
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    assert not [
        finding for finding in result.snapshot.findings
        if finding.code == "CONSTRAINT:REQUIRE_EXECUTABLE_PROOF"
    ]


def test_constraint_change_changes_configuration_fingerprint(tmp_path: Path) -> None:
    _write_project(tmp_path, with_evidence=True)
    first = load_config(tmp_path)
    first_fingerprint = configuration_fingerprint(
        first, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    path = tmp_path / ".quarto-needs.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'severity = "error"', 'severity = "warning"'
        ),
        encoding="utf-8",
    )
    second = load_config(tmp_path)
    second_fingerprint = configuration_fingerprint(
        second, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    assert first_fingerprint != second_fingerprint


def test_invalid_constraint_is_configuration_error_at_load(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[constraints.BAD]
kind = "required-path"
scope = "approved-requirements"
relations = ["verified-by"]
python = "eval('nope')"
''',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_config(tmp_path)
