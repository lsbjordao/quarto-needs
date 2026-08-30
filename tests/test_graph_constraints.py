from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.graph_constraints import (
    GraphConstraintError,
    compile_graph_constraint,
    compile_graph_constraints,
    evaluate_graph_constraints,
)


def _project(tmp_path: Path, body: str):
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"
[types.test-case]
role = "verification"
[types.evidence]
role = "evidence"
[types.component]
role = "architecture-element"

[queries.requirements]
all = [{ field = "type", op = "eq", value = "functional-requirement" }]

[queries.components]
all = [{ field = "type", op = "eq", value = "component" }]
''',
        encoding="utf-8",
    )
    (tmp_path / "model.qmd").write_text(body, encoding="utf-8")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return config, result.snapshot


def test_required_path_finds_requirement_test_evidence_chain(tmp_path: Path) -> None:
    config, snapshot = _project(
        tmp_path,
        '''::: {.need #FUN-1 type="functional-requirement" status="approved" verified-by="TC-1"}
## Requirement
:::
::: {.need #FUN-2 type="functional-requirement" status="approved" verified-by="TC-2"}
## Broken requirement
:::
::: {.need #TC-1 type="test-case" status="passed" evidenced-by="EVD-1"}
## Test
:::
::: {.need #TC-2 type="test-case" status="passed"}
## Test without evidence
:::
::: {.need #EVD-1 type="evidence" status="verified"}
## Evidence
:::
''',
    )
    constraints = compile_graph_constraints(
        {
            "REQ_TO_EVIDENCE": {
                "kind": "required-path",
                "scope": "requirements",
                "relations": ["verified-by", "evidenced-by"],
                "target-role": "evidence",
                "severity": "error",
            }
        }
    )
    findings = evaluate_graph_constraints(constraints, snapshot, config)
    assert [(item.code, item.object_id) for item in findings] == [
        ("CONSTRAINT:REQ_TO_EVIDENCE", "FUN-2")
    ]


def test_required_path_accepts_inverse_authored_verification_step(tmp_path: Path) -> None:
    config, snapshot = _project(
        tmp_path,
        '''::: {.need #FUN-1 type="functional-requirement" status="approved"}
## Requirement
:::
::: {.need #TC-1 type="test-case" status="passed" verifies="FUN-1" evidenced-by="EVD-1"}
## Test
:::
::: {.need #EVD-1 type="evidence" status="verified"}
## Evidence
:::
''',
    )
    constraints = compile_graph_constraints(
        {
            "REQ_TO_EVIDENCE": {
                "kind": "required-path",
                "scope": "requirements",
                "relations": ["verified-by", "evidenced-by"],
                "target-role": "evidence",
            }
        }
    )
    assert evaluate_graph_constraints(constraints, snapshot, config) == ()


def test_forbidden_cycle_reports_explicit_cycle_witness(tmp_path: Path) -> None:
    config, snapshot = _project(
        tmp_path,
        '''::: {.need #COMP-A type="component" status="implemented" depends-on="COMP-B"}
## A
:::
::: {.need #COMP-B type="component" status="implemented" depends-on="COMP-C"}
## B
:::
::: {.need #COMP-C type="component" status="implemented" depends-on="COMP-A"}
## C
:::
''',
    )
    constraints = compile_graph_constraints(
        {
            "ACYCLIC_COMPONENTS": {
                "kind": "forbidden-cycle",
                "scope": "components",
                "relations": ["depends-on"],
            }
        }
    )
    findings = evaluate_graph_constraints(constraints, snapshot, config)
    assert len(findings) == 1
    assert findings[0].code == "CONSTRAINT:ACYCLIC_COMPONENTS"
    cycle = findings[0].properties["cycle"]
    assert cycle[0] == cycle[-1]
    assert set(cycle[:-1]) == {"COMP-A", "COMP-B", "COMP-C"}


def test_connected_constraint_can_scope_orphans(tmp_path: Path) -> None:
    config, snapshot = _project(
        tmp_path,
        '''::: {.need #COMP-A type="component" status="implemented" references="COMP-B"}
## A
:::
::: {.need #COMP-B type="component" status="implemented"}
## B
:::
::: {.need #COMP-C type="component" status="implemented"}
## C
:::
''',
    )
    constraints = compile_graph_constraints(
        {
            "CONNECTED_COMPONENTS": {
                "kind": "connected",
                "scope": "components",
                "minimum": 1,
                "severity": "warning",
            }
        }
    )
    findings = evaluate_graph_constraints(constraints, snapshot, config)
    assert [(item.object_id, item.severity) for item in findings] == [
        ("COMP-C", "warning")
    ]


def test_max_relations_uses_logical_relation_view_and_target_role(tmp_path: Path) -> None:
    config, snapshot = _project(
        tmp_path,
        '''::: {.need #FUN-1 type="functional-requirement" status="approved" verified-by="TC-1;TC-2"}
## Requirement
:::
::: {.need #TC-1 type="test-case" status="passed"}
## Test 1
:::
::: {.need #TC-2 type="test-case" status="passed"}
## Test 2
:::
''',
    )
    constraints = compile_graph_constraints(
        {
            "ONE_TEST": {
                "kind": "max-relations",
                "scope": "requirements",
                "relations": ["verified-by"],
                "target-role": "verification",
                "maximum": 1,
            }
        }
    )
    findings = evaluate_graph_constraints(constraints, snapshot, config)
    assert len(findings) == 1
    assert findings[0].object_id == "FUN-1"
    assert findings[0].properties["targets"] == ["TC-1", "TC-2"]


@pytest.mark.parametrize(
    "raw",
    [
        {"kind": "required-path", "scope": "requirements", "relations": []},
        {"kind": "forbidden-cycle", "relations": ["unknown"]},
        {"kind": "connected", "scope": "requirements", "minimum": 0},
        {"kind": "max-relations", "scope": "requirements", "relations": ["verified-by"], "maximum": 0},
        {"kind": "python", "scope": "requirements", "relations": ["verified-by"]},
        {"kind": "required-path", "scope": "requirements", "relations": ["verified-by"], "eval": "open('/etc/passwd')"},
    ],
)
def test_graph_constraint_grammar_rejects_unbounded_or_invalid_forms(raw) -> None:
    with pytest.raises(GraphConstraintError):
        compile_graph_constraint("BAD", raw)
