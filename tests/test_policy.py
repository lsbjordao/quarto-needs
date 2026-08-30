from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.policy import PolicyError, compile_policies, compile_policy, evaluate_policies


def _project(tmp_path: Path):
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
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Verified requirement
Body.
:::

::: {.need #FUN-002 type="functional-requirement" status="approved"}
## Missing verification
Body.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Body.
:::
''',
        encoding="utf-8",
    )
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


def test_policy_compiler_accepts_inverse_authoring_label_but_stores_canonical_relation() -> None:
    spec = compile_policy(
        "INVERSE_LABEL",
        {
            "scope": "approved-requirements",
            "assert-relation": "validated-by",
        },
    )
    assert spec.assert_relation == "verified-by"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"scope": "x", "assert-relation": "verified-by", "python": "eval('x')"}, "unknown keys"),
        ({"scope": "x", "assert-relation": "not-a-relation"}, "Unsupported relation type"),
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
