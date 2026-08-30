from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.derived import (
    DerivedError,
    compile_derived_field,
    compile_derived_fields,
    compile_variant,
    compile_variants,
    materialize_derived,
    materialize_variants,
)


def _project(tmp_path: Path):
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"

[types.test-case]
role = "verification"

[types.evidence]
role = "evidence"

[queries.approved]
all = [
  { field = "type", op = "eq", value = "functional-requirement" },
  { field = "status", op = "eq", value = "approved" },
]
sort = ["id:asc"]

[queries.one-requirement]
all = [
  { field = "id", op = "eq", value = "FUN-001" },
]
sort = ["id:asc"]
''',
        encoding="utf-8",
    )
    (tmp_path / "model.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requirement
:::

::: {.need #TC-001 type="test-case" status="passed" evidenced-by="EVD-001"}
## Test
:::

::: {.need #EVD-001 type="evidence" status="verified"}
## Evidence
:::
''',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return config, result.snapshot


def test_relation_count_and_path_exists_are_deterministic(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path)
    specs = compile_derived_fields(
        {
            "verification-count": {
                "scope": "approved",
                "operation": "relation-count",
                "relation": "verified-by",
                "target-role": "verification",
            },
            "has-evidence-path": {
                "scope": "approved",
                "operation": "path-exists",
                "relations": ["verified-by", "evidenced-by"],
                "target-role": "evidence",
            },
        }
    )
    assert materialize_derived(specs, snapshot, config) == {
        "FUN-001": {
            "has-evidence-path": True,
            "verification-count": 1,
        }
    }


def test_derived_relation_count_accepts_inverse_authoring(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path)
    specs = compile_derived_fields(
        {
            "verification-count": {
                "scope": "approved",
                "operation": "relation-count",
                "relation": "verified-by",
            }
        }
    )
    assert materialize_derived(specs, snapshot, config)["FUN-001"]["verification-count"] == 1


def test_variant_expands_bounded_relation_closure(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path)
    variants = compile_variants(
        {
            "assurance-slice": {
                "scope": "one-requirement",
                "relations": ["verified-by", "evidenced-by"],
                "depth": 2,
            }
        }
    )
    assert materialize_variants(variants, snapshot, config) == {
        "assurance-slice": ("EVD-001", "FUN-001", "TC-001")
    }


@pytest.mark.parametrize(
    "raw",
    [
        {"scope": "approved", "operation": "python", "relation": "verified-by"},
        {"scope": "approved", "operation": "relation-count", "relations": ["verified-by"]},
        {"scope": "approved", "operation": "path-exists", "relation": "verified-by"},
        {"scope": "approved", "operation": "relation-count", "relation": "verified-by", "eval": "1+1"},
    ],
)
def test_derived_grammar_rejects_unbounded_forms(raw) -> None:
    with pytest.raises(DerivedError):
        compile_derived_field("BAD", raw)


@pytest.mark.parametrize(
    "raw",
    [
        {"scope": "approved", "depth": 1},
        {"scope": "approved", "relations": ["verified-by"], "depth": 0},
        {"scope": "approved", "relations": ["verified-by"], "depth": 11},
        {"scope": "approved", "relations": ["verified-by"], "script": "x"},
    ],
)
def test_variant_grammar_rejects_unbounded_forms(raw) -> None:
    with pytest.raises(DerivedError):
        compile_variant("BAD", raw)
