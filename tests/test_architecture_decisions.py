from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config


def write_project(
    root: Path,
    *,
    decision_id: str = "ADR-001",
    status: str = "accepted",
    revisit_after: str | None = None,
) -> None:
    (root / ".quarto-needs.toml").write_text(
        '''profile = "strict"

[types.architecture-decision]
id-prefix = "ADR-"
role = "decision"
allowed-statuses = ["proposed", "accepted", "rejected", "deprecated", "superseded"]
required-attributes = ["date", "decision-makers", "tags"]

[types.non-functional-requirement]
id-prefix = "NFR-"
role = "requirement"

[types.component]
id-prefix = "COMP-"
role = "architecture-element"

[types.test-case]
id-prefix = "TC-"
role = "verification"

[relations."addresses"]
allowed-source-types = ["architecture-decision"]
allowed-target-types = ["non-functional-requirement"]

[relations."applies-to"]
allowed-source-types = ["architecture-decision"]
allowed-target-types = ["component"]

[relations."confirmed-by"]
allowed-source-types = ["architecture-decision"]
allowed-target-types = ["test-case"]

[rules.DEC001]
enabled = true
[rules.DEC002]
enabled = true
[rules.DEC003]
enabled = true
[rules.DEC004]
enabled = true
[rules.DEC005]
enabled = true
[rules.DEC006]
enabled = true
''',
        encoding="utf-8",
    )
    revisit = f"revisit-after: {revisit_after}\n" if revisit_after else ""
    (root / "objects.qmd").write_text(
        f'''::: {{.need #NFR-001 type=non-functional-requirement status=draft}}
## Driver
Body.
:::

::: {{.need #COMP-001 type=component status=implemented}}
## Component
Body.
:::

::: {{.need #TC-001 type=test-case status=passed}}
## Confirmation
Body.
:::

::: {{.need #{decision_id} type=architecture-decision status={status}}}
date: 2026-08-28
decision-makers: Architecture Team
tags: architecture
{revisit}addresses: NFR-001
applies-to: COMP-001
confirmed-by: TC-001

## Choose architecture

### Context and Problem Statement
Context.

### Decision Outcome
Outcome.
:::
''',
        encoding="utf-8",
    )


def test_accepted_decision_passes_decision_governance(tmp_path: Path) -> None:
    write_project(tmp_path)
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)

    assert result.snapshot is not None
    decision_codes = {finding.code for finding in result.findings if finding.code.startswith("DEC")}
    assert decision_codes == set()
    assert config.id_prefixes["architecture-decision"] == "ADR-"
    assert config.type_roles["architecture-decision"] == "decision"


def test_configured_id_prefix_is_enforced(tmp_path: Path) -> None:
    write_project(tmp_path, decision_id="DECISION-001")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)

    assert result.snapshot is not None
    assert any(finding.code == "ID001" and finding.object_id == "DECISION-001" for finding in result.findings)


def test_allowed_statuses_are_enforced(tmp_path: Path) -> None:
    write_project(tmp_path, status="approved")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)

    assert result.snapshot is not None
    assert any(finding.code == "OBJ001" and finding.object_id == "ADR-001" for finding in result.findings)


def test_accepted_decision_without_driver_is_reported(tmp_path: Path) -> None:
    write_project(tmp_path)
    path = tmp_path / "objects.qmd"
    path.write_text(path.read_text(encoding="utf-8").replace("addresses: NFR-001\n", ""), encoding="utf-8")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)

    assert result.snapshot is not None
    assert any(finding.code == "DEC001" and finding.object_id == "ADR-001" for finding in result.findings)


def test_accepted_decision_overdue_for_revisit_is_reported(tmp_path: Path, monkeypatch) -> None:
    # 2027-01-01T00:00:00Z
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1798761600")
    write_project(tmp_path, revisit_after="2026-12-01")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)

    assert result.snapshot is not None
    finding = next(
        finding for finding in result.findings
        if finding.code == "DEC006" and finding.object_id == "ADR-001"
    )
    assert finding.properties["reason"] == "overdue"
    assert finding.properties["due"] == "2026-12-01"
    assert finding.properties["referenceDate"] == "2027-01-01"
