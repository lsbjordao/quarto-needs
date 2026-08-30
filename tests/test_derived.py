from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.baseline import build_baseline
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.derived import (
    DerivedError,
    compile_derived_field,
    compile_derived_fields,
    compile_variant,
    compile_variants,
    materialize_derived,
    materialize_variants,
)
from quarto_needs.fingerprints import configuration_fingerprint
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


BASE_CONFIG = '''[types.functional-requirement]
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
'''

DERIVED_CONFIG = '''
[derived.verification-count]
scope = "approved"
operation = "relation-count"
relation = "verified-by"
target-role = "verification"

[derived.has-evidence-path]
scope = "approved"
operation = "path-exists"
relations = ["verified-by", "evidenced-by"]
target-role = "evidence"

[variants.assurance-slice]
scope = "one-requirement"
relations = ["verified-by", "evidenced-by"]
depth = 2
'''

MODEL = '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requirement
:::

::: {.need #TC-001 type="test-case" status="passed" evidenced-by="EVD-001"}
## Test
:::

::: {.need #EVD-001 type="evidence" status="verified"}
## Evidence
:::
'''


def _project(tmp_path: Path, *, integrated: bool = False):
    (tmp_path / ".quarto-needs.toml").write_text(
        BASE_CONFIG + (DERIVED_CONFIG if integrated else ""), encoding="utf-8"
    )
    (tmp_path / "model.qmd").write_text(MODEL, encoding="utf-8")
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


def test_integrated_config_materializes_separate_snapshot_projections(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path, integrated=True)
    assert config.canonical_document()["derived"]["verification-count"] == {
        "scope": "approved",
        "operation": "relation-count",
        "relation": "verified-by",
        "target-role": "verification",
    }
    assert snapshot.derived == {
        "FUN-001": {
            "has-evidence-path": True,
            "verification-count": 1,
        }
    }
    assert snapshot.variants == {
        "assurance-slice": ("EVD-001", "FUN-001", "TC-001")
    }
    assert snapshot.variant_fingerprint
    assert "verification-count" not in snapshot.objects_by_id["FUN-001"].attributes


def test_derived_and_variant_definitions_change_configuration_fingerprint(tmp_path: Path) -> None:
    _project(tmp_path, integrated=True)
    first = load_config(tmp_path)
    first_fp = configuration_fingerprint(
        first, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    path = tmp_path / ".quarto-needs.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("depth = 2", "depth = 1"),
        encoding="utf-8",
    )
    second = load_config(tmp_path)
    second_fp = configuration_fingerprint(
        second, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    assert first_fp != second_fp


def test_derived_projection_changes_semantic_fingerprint(tmp_path: Path) -> None:
    _, plain = _project(tmp_path)
    plain_semantic = plain.semantic_graph_fingerprint
    _, projected = _project(tmp_path, integrated=True)
    assert projected.semantic_graph_fingerprint != plain_semantic


def test_baseline_persists_derived_and_variants_separately(tmp_path: Path) -> None:
    config, snapshot = _project(tmp_path, integrated=True)
    baseline = build_baseline(snapshot, config)
    assert baseline["derived"]["FUN-001"]["verification-count"] == 1
    assert baseline["variants"]["assurance-slice"] == ["EVD-001", "FUN-001", "TC-001"]
    assert baseline["variantFingerprint"] == snapshot.variant_fingerprint
    obj = next(item for item in baseline["objects"] if item["id"] == "FUN-001")
    assert "verification-count" not in obj["attributes"]


def test_invalid_derived_or_variant_config_fails_load(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        BASE_CONFIG
        + '''\n[derived.BAD]\nscope = "approved"\noperation = "eval"\nrelation = "verified-by"\n''',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_config(tmp_path)


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
