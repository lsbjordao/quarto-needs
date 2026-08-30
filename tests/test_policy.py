from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.fingerprints import configuration_fingerprint
from quarto_needs.policy import PolicyError, compile_policies, compile_policy, evaluate_policies
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def _write_project(tmp_path: Path, *, inverse: bool = False, with_policy: bool = False) -> None:
    policy = '''
[policies.APPROVED_REQUIRES_TEST]
scope = "approved-functional"
assert-relation = "verified-by"
target-role = "verification"
minimum = 1
severity = "error"
''' if with_policy else ""
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
id-prefix = "FUN-"
role = "requirement"
allowed-statuses = ["approved"]

[types.test-case]
id-prefix = "TC-"
role = "verification"
allowed-statuses = ["passed"]

[relations."verified-by"]
allowed-source-types = ["functional-requirement"]
allowed-target-types = ["test-case"]

[queries.approved-functional]
all = [
  { field = "type", op = "eq", value = "functional-requirement" },
  { field = "status", op = "eq", value = "approved" },
]
sort = ["id:asc"]
''' + policy,
        encoding="utf-8",
    )
    if inverse:
        relation_on_requirement = ""
        relation_on_test = ' verifies="FUN-001"'
    else:
        relation_on_requirement = ' verified-by="TC-001"'
        relation_on_test = ""
    (tmp_path / "requirements.qmd").write_text(
        f'''::: {{.need #FUN-001 type="functional-requirement" status="approved"{relation_on_requirement}}}
## Verified requirement
Body.
:::

::: {{.need #FUN-002 type="functional-requirement" status="approved"}}
## Missing verification
Body.
:::

::: {{.need #TC-001 type="test-case" status="passed"{relation_on_test}}}
## Verification
Body.
:::
''',
        encoding="utf-8",
    )


def _project(tmp_path: Path, *, inverse: bool = False):
    _write_project(tmp_path, inverse=inverse)
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return config, result.snapshot


def test_policy_compiler_normalizes_relation_and_evaluates_named_scope(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path)
    policies = compile_policies(
        {
            "APPROVED_REQUIRES_TEST": {
                "scope": "approved-functional",
                "assert-relation": "verified-by",
                "target-role": "verification",
                "minimum": 1,
                "severity": "error",
            }
        }
    )

    findings = evaluate_policies(policies, snapshot, config)
    assert [finding.code for finding in findings] == ["POLICY:APPROVED_REQUIRES_TEST"]
    finding = findings[0]
    assert finding.object_id == "FUN-002"
    assert finding.severity == "error"
    assert finding.properties["relation"] == "verified-by"
    assert finding.properties["targetRole"] == "verification"
    assert finding.properties["actual"] == 0
    assert finding.properties["minimum"] == 1


def test_policy_relation_view_accepts_inverse_authored_edge(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path, inverse=True)
    policies = compile_policies(
        {
            "APPROVED_REQUIRES_TEST": {
                "scope": "approved-functional",
                "assert-relation": "verified-by",
                "target-role": "verification",
            }
        }
    )
    findings = evaluate_policies(policies, snapshot, config)
    assert [finding.object_id for finding in findings] == ["FUN-002"]


def test_policy_compiler_accepts_alias_but_stores_catalog_relation() -> None:
    spec = compile_policy(
        "VALIDATION_LABEL",
        {
            "scope": "approved-requirements",
            "assert-relation": "validated-by",
        },
    )
    assert spec.assert_relation == "validated-by"


def test_relation_catalog_exposes_inverse_without_policy_side_table() -> None:
    assert DEFAULT_RELATION_CATALOG.inverse_v1_name("verified-by") == "verifies"
    assert DEFAULT_RELATION_CATALOG.inverse_v1_name("verifies") == "verified-by"
    assert DEFAULT_RELATION_CATALOG.inverse_v1_name("addresses") == "addressed-by"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"scope": "x", "assert-relation": "verified-by", "python": "eval('x')"}, "unknown keys"),
        ({"scope": "x", "assert-relation": "not-a-relation"}, "Unknown relation type"),
        ({"scope": "x", "assert-relation": "verified-by", "minimum": 0}, "integer >= 1"),
        ({"scope": "x", "assert-relation": "verified-by", "severity": "fatal"}, "error, warning, info"),
        ({"scope": "", "assert-relation": "verified-by"}, "scope must be a non-empty string"),
    ],
)
def test_policy_compiler_rejects_values_outside_bounded_grammar(raw, message: str) -> None:
    with pytest.raises(PolicyError, match=message):
        compile_policy("BAD", raw)


def test_policy_scope_must_resolve_to_existing_safe_named_query(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path)
    policies = compile_policies(
        {"BAD_SCOPE": {"scope": "does-not-exist", "assert-relation": "verified-by"}}
    )
    with pytest.raises(PolicyError, match="does-not-exist"):
        evaluate_policies(policies, snapshot, config)


def test_configured_policy_is_part_of_canonical_document_and_analysis(tmp_path: Path) -> None:
    _write_project(tmp_path, with_policy=True)
    config = load_config(tmp_path)
    canonical = config.canonical_document()
    assert canonical["policies"] == {
        "APPROVED_REQUIRES_TEST": {
            "scope": "approved-functional",
            "assert-relation": "verified-by",
            "target-role": "verification",
            "minimum": 1,
            "severity": "error",
        }
    }

    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    findings = [
        finding for finding in result.snapshot.findings
        if finding.code == "POLICY:APPROVED_REQUIRES_TEST"
    ]
    assert [(finding.object_id, finding.severity) for finding in findings] == [
        ("FUN-002", "error")
    ]


def test_policy_change_changes_configuration_fingerprint(tmp_path: Path) -> None:
    _write_project(tmp_path, with_policy=True)
    first = load_config(tmp_path)
    first_fingerprint = configuration_fingerprint(
        first, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    config_path = tmp_path / ".quarto-needs.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'severity = "error"', 'severity = "warning"'
        ),
        encoding="utf-8",
    )
    second = load_config(tmp_path)
    second_fingerprint = configuration_fingerprint(
        second, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    assert first_fingerprint != second_fingerprint


def test_invalid_policy_is_configuration_error_at_load_time(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[policies.BAD]
scope = "approved-requirements"
assert-relation = "verified-by"
python = "__import__('os').system('echo nope')"
''',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_config(tmp_path)
